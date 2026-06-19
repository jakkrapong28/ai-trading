"""MT5 Bridge Server — run this on a Windows machine with MetaTrader 5.

The `MetaTrader5` Python package only works on Windows (it talks to a running
MT5 terminal over IPC). This FastAPI app exposes the terminal's live prices and
a connect/disconnect control over HTTP so the main backend (engines/providers/
mt5_bridge.py) can poll prices and the frontend "MT5 Connection" page can log in.

IMPORTANT — Python version on this machine:
    The MetaTrader5 package is installed only in Python 3.13 (the backend venv is
    3.14 and cannot import it). Launch this server with py -3.13, e.g.:
        py -3.13 tools/mt5_bridge_server.py
    (or use tools/run_mt5_bridge.ps1)

Endpoints:
    POST /connect    {login, password, server}   -> log into the trade account
    POST /disconnect                              -> mt5.shutdown(), forget creds
    GET  /status                                  -> connection + account info
    GET  /health                                  -> {"connected": bool}
    GET  /ticks?symbols=XAUUSDm,BTCUSDm           -> live bid/ask per symbol

Credentials are saved to tools/.mt5_session.json (gitignored) so the server
auto-reconnects on restart. The password is never returned by any endpoint.
"""
import json
import os
import threading
from datetime import datetime, timedelta

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - only importable on Windows + py3.13
    raise SystemExit(
        "MetaTrader5 package not available. Run this server on Windows with the "
        "MT5 terminal installed, using the Python that has it: py -3.13 "
        "(pip install MetaTrader5 fastapi uvicorn)."
    )

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
import uvicorn

API_KEY = os.getenv("MT5_BRIDGE_KEY", "")
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mt5_session.json")

app = FastAPI(title="MT5 Bridge")

# MT5's IPC is not thread-safe; FastAPI runs sync endpoints in a threadpool, so
# serialize every mt5.* call behind one lock.
_lock = threading.Lock()
# In-memory view of the active session (password kept only to re-init on restart).
_session = {"login": None, "server": None, "connected": False}


class ConnectRequest(BaseModel):
    login: int
    password: str
    server: str


def _check_key(x_api_key: str):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="bad api key")


def _save_session(login: int, password: str, server: str):
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"login": login, "password": password, "server": server}, f)
    except Exception as e:  # pragma: no cover
        print(f"[mt5-bridge] could not save session: {e}")


def _clear_session_file():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception as e:  # pragma: no cover
        print(f"[mt5-bridge] could not clear session: {e}")


def _reconnect_from_file() -> bool:
    """Re-establish the MT5 session from the saved credentials (must hold _lock)."""
    if not os.path.exists(SESSION_FILE):
        return False
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        ok, _ = _do_connect(int(s["login"]), s["password"], s["server"])
        return ok
    except Exception:
        return False


def _account_payload():
    """Build a status payload from the live terminal (must hold _lock)."""
    ti = mt5.terminal_info()
    ai = mt5.account_info()
    connected = bool(ti and ti.connected and ai)
    # Self-heal: if the session dropped (terminal restart / network) but creds are
    # saved, transparently reconnect so the dashboard never silently falls back.
    if not connected and _reconnect_from_file():
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        connected = bool(ti and ti.connected and ai)
    _session["connected"] = connected
    out = {
        "connected": connected,
        "login": _session.get("login"),
        "server": _session.get("server"),
        "terminal_build": getattr(ti, "build", None) if ti else None,
    }
    if ai:
        out["account"] = {
            "login": ai.login,
            "server": ai.server,
            "name": ai.name,
            "balance": ai.balance,
            "equity": ai.equity,
            "margin_free": ai.margin_free,
            "currency": ai.currency,
            "leverage": ai.leverage,
            "company": ai.company,
        }
    return out


def _do_connect(login: int, password: str, server: str):
    """Initialize MT5 against the given account (must hold _lock)."""
    mt5.shutdown()  # drop any prior session so creds actually take effect
    ok = mt5.initialize(login=login, password=password, server=server)
    if not ok:
        code, msg = mt5.last_error()
        return False, f"{msg} (code {code})"
    _session.update({"login": login, "server": server, "connected": True})
    return True, "connected"


@app.on_event("startup")
def _startup():
    """Auto-reconnect from the saved session if present."""
    if not os.path.exists(SESSION_FILE):
        print("[mt5-bridge] no saved session — waiting for /connect.")
        return
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
        with _lock:
            ok, msg = _do_connect(int(s["login"]), s["password"], s["server"])
        print(f"[mt5-bridge] auto-connect {s.get('login')}@{s.get('server')}: {msg}")
    except Exception as e:
        print(f"[mt5-bridge] auto-connect failed: {e}")


@app.on_event("shutdown")
def _shutdown():
    with _lock:
        mt5.shutdown()


@app.post("/connect")
def connect(req: ConnectRequest, x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    with _lock:
        ok, msg = _do_connect(req.login, req.password, req.server)
        if ok:
            _save_session(req.login, req.password, req.server)
            payload = _account_payload()
        else:
            payload = {"connected": False, "login": req.login, "server": req.server}
    if not ok:
        return {"status": "failed", "message": msg, **payload}
    return {"status": "success", "message": "MT5 connected", **payload}


@app.post("/disconnect")
def disconnect(x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    with _lock:
        mt5.shutdown()
        _session.update({"login": None, "server": None, "connected": False})
        _clear_session_file()
    return {"status": "success", "message": "MT5 disconnected", "connected": False}


@app.get("/status")
def status(x_api_key: str = Header(default="")):
    _check_key(x_api_key)
    with _lock:
        try:
            return _account_payload()
        except Exception as e:
            return {"connected": False, "error": str(e)}


@app.get("/health")
def health():
    with _lock:
        info = mt5.terminal_info()
        return {"connected": bool(info and info.connected)}


@app.get("/ticks")
def ticks(
    symbols: str = Query(..., description="comma-separated symbols"),
    x_api_key: str = Header(default=""),
):
    _check_key(x_api_key)
    out = []
    with _lock:
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


@app.get("/orders")
def orders(days: int = 30, x_api_key: str = Header(default="")):
    """Account trade history mapped to the dashboard Order shape:
    open positions (status OPEN, floating PnL) + closed deals (status CLOSED)."""
    _check_key(x_api_key)
    out = []
    with _lock:
        # --- open positions ---
        for p in (mt5.positions_get() or []):
            out.append({
                "id": str(p.ticket),
                "symbol": p.symbol,
                "action": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                "volume": p.volume,
                "entry_price": p.price_open,
                "exit_price": 0.0,
                "sl_price": p.sl,
                "tp_price": p.tp,
                "pnl": p.profit,                       # floating
                "fee": float(getattr(p, "swap", 0.0) or 0.0),
                "status": "OPEN",
                "opened_at": datetime.utcfromtimestamp(p.time).isoformat(),
                "closed_at": None,
            })
        # --- closed history (the OUT deal of each round-trip carries realized PnL) ---
        frm = datetime.now() - timedelta(days=days)
        to = datetime.now() + timedelta(days=1)
        for d in (mt5.history_deals_get(frm, to) or []):
            if d.entry != mt5.DEAL_ENTRY_OUT:
                continue
            # The closing deal type is opposite of the original position direction.
            action = "BUY" if d.type == mt5.DEAL_TYPE_SELL else "SELL"
            out.append({
                "id": str(d.ticket),
                "symbol": d.symbol,
                "action": action,
                "volume": d.volume,
                "entry_price": 0.0,
                "exit_price": d.price,
                "sl_price": 0.0,
                "tp_price": 0.0,
                "pnl": d.profit,
                "fee": float((getattr(d, "commission", 0.0) or 0.0) + (getattr(d, "swap", 0.0) or 0.0)),
                "status": "CLOSED",
                "opened_at": datetime.utcfromtimestamp(d.time).isoformat(),
                "closed_at": datetime.utcfromtimestamp(d.time).isoformat(),
            })
    return {"orders": out}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("MT5_BRIDGE_PORT", "8765")))
