"""TwelveData WebSocket provider — live stocks + forex + metals (XAU/USD).

Primary source for stocks/gold. Works cross-platform (unlike MetaTrader5),
covers US stocks + XAU/USD in real time, and the project already has a
TWELVEDATA_API_KEY in .env. Free tier WS allows up to 8 symbols.

Docs: wss://ws.twelvedata.com/v1/quotes/price?apikey=KEY
  subscribe -> {"action":"subscribe","params":{"symbols":"AAPL,XAU/USD"}}
  message   -> {"event":"price","symbol":"AAPL","price":123.4,...}
A heartbeat ({"action":"heartbeat"}) must be sent periodically to stay alive.
"""
import asyncio
import json
import logging
import os

import websockets

from backend.engines.providers.base import MarketDataProvider, emit_tick

logger = logging.getLogger("market-data.twelvedata")

# Internal ticker -> TwelveData symbol. Stocks map 1:1; gold needs XAU/USD.
SYMBOL_MAP = {
    "AAPL": "AAPL",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "XAUUSD": "XAU/USD",
}
# Reverse map to translate TwelveData symbols back to internal tickers.
REVERSE_MAP = {v: k for k, v in SYMBOL_MAP.items()}

# Typical fractional half-spread used to synthesize bid/ask (price-only feed).
HALF_SPREAD = 0.0005  # 5 bps


class TwelveDataProvider(MarketDataProvider):
    name = "twelvedata"

    def __init__(self, event_bus):
        super().__init__(event_bus)
        self.api_key = os.getenv("TWELVEDATA_API_KEY", "")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def _heartbeat(self, ws):
        try:
            while True:
                await asyncio.sleep(10)
                await ws.send(json.dumps({"action": "heartbeat"}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def stream(self) -> None:
        if not self.enabled:
            logger.info("TWELVEDATA_API_KEY not set — TwelveData provider disabled.")
            return

        ws_url = f"wss://ws.twelvedata.com/v1/quotes/price?apikey={self.api_key}"
        symbols = ",".join(SYMBOL_MAP.values())

        while True:
            hb_task = None
            try:
                logger.info("Connecting to TwelveData WS...")
                async with websockets.connect(ws_url) as ws:
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "params": {"symbols": symbols},
                    }))
                    hb_task = asyncio.create_task(self._heartbeat(ws))

                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        event = data.get("event")

                        if event == "price":
                            td_symbol = data.get("symbol")
                            ticker = REVERSE_MAP.get(td_symbol, td_symbol)
                            price = data.get("price")
                            if price is None:
                                continue
                            price = float(price)
                            volume = float(data.get("day_volume") or 0.0)
                            await emit_tick(
                                self.event_bus,
                                ticker=ticker,
                                price=price,
                                bid=price * (1 - HALF_SPREAD),
                                ask=price * (1 + HALF_SPREAD),
                                volume=volume,
                                source="twelvedata",
                            )
                        elif event == "subscribe-status":
                            ok = [s.get("symbol") for s in data.get("success", [])]
                            fails = [s.get("symbol") for s in data.get("fails", [])]
                            logger.info(f"TwelveData streaming: {ok}")
                            if fails:
                                logger.warning(
                                    f"TwelveData plan rejected {fails} — these will fall "
                                    "back to Finnhub/MT5/mock. Upgrade the TwelveData plan "
                                    "or wire the MT5 bridge for full live stock coverage."
                                )
            except asyncio.CancelledError:
                if hb_task:
                    hb_task.cancel()
                break
            except Exception as e:
                logger.error(f"TwelveData WS error: {e}. Reconnecting in 5s...")
                if hb_task:
                    hb_task.cancel()
                await asyncio.sleep(5)
