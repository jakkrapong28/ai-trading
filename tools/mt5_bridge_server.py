"""MT5 Bridge Server — run this on a Windows machine/VPS with MetaTrader 5.

The `MetaTrader5` Python package only works on Windows (it talks to a running
MT5 terminal over IPC). This tiny FastAPI app exposes the terminal's live
prices over HTTP so the main backend (running on Mac/Linux) can poll them via
engines/providers/mt5_bridge.py.

Setup (on Windows):
    1. Install MetaTrader 5 terminal and log into your broker account.
    2. pip install MetaTrader5 fastapi uvicorn
    3. set MT5_BRIDGE_KEY=some-shared-secret   (optional but recommended)
    4. python mt5_bridge_server.py
    5. Expose port 8765 to your backend (VPS firewall / tunnel).

Then on the backend set in .env:
    MT5_BRIDGE_URL=http://<windows-host>:8765
    MT5_BRIDGE_KEY=some-shared-secret

Endpoint:
    GET /ticks?symbols=XAUUSD,EURUSD  ->
        {"ticks":[{"symbol","bid","ask","last","volume","time"}, ...]}
"""
import os

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - only importable on Windows
    raise SystemExit(
        "MetaTrader5 package not available. Run this script on Windows with "
        "the MT5 terminal installed: pip install MetaTrader5"
    )

from fastapi import FastAPI, Header, HTTPException, Query
import uvicorn

API_KEY = os.getenv("MT5_BRIDGE_KEY", "")
app = FastAPI(title="MT5 Bridge")


@app.on_event("startup")
def _init_mt5():
    if not mt5.initialize():
        raise RuntimeError(f"mt5.initialize() failed: {mt5.last_error()}")


@app.on_event("shutdown")
def _shutdown_mt5():
    mt5.shutdown()


@app.get("/health")
def health():
    info = mt5.terminal_info()
    return {"connected": bool(info and info.connected)}


@app.get("/ticks")
def ticks(
    symbols: str = Query(..., description="comma-separated symbols"),
    x_api_key: str = Header(default=""),
):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="bad api key")

    out = []
    for sym in [s.strip() for s in symbols.split(",") if s.strip()]:
        # Ensure the symbol is selected in Market Watch before quoting.
        mt5.symbol_select(sym, True)
        tick = mt5.symbol_info_tick(sym)
        if tick is None:
            continue
        out.append({
            "symbol": sym,
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last or tick.bid,
            "volume": float(tick.volume),
            "time": tick.time,
        })
    return {"ticks": out}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MT5_BRIDGE_PORT", "8765")))
