from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager

from backend.shared.events.core import EventBus, CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS, CH_AI_JOURNAL, CH_NEWS, CH_RISK_APPROVED, CH_RISK_REJECTED, CH_EXEC_OPENED, CH_EXEC_CLOSED, CH_PORTFOLIO_UPDATED
from backend.shared.database.core import Base, engine, SessionLocal
from backend.shared.database.models import Trade, PerformanceMetric

from backend.engines.market_data import start_market_data_engine
from backend.engines.news_intelligence import start_news_intelligence_engine
from backend.engines.market_regime import start_market_regime_engine
from backend.engines.strategy import start_strategy_engine
from backend.engines.risk import start_risk_engine
from backend.engines.execution import start_execution_engine
from backend.engines.portfolio import start_portfolio_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("api-gateway")

# Global Event Bus
event_bus = EventBus()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Database
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")
    
    # Start Engines
    logger.info("Starting AI Trading Engines...")
    start_market_data_engine(event_bus)
    start_news_intelligence_engine(event_bus)
    start_market_regime_engine(event_bus)
    start_strategy_engine(event_bus)
    start_risk_engine(event_bus)
    start_execution_engine(event_bus)
    start_portfolio_engine(event_bus)
    
    yield
    
    await event_bus.close()

app = FastAPI(title="AI Trading System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Websocket manager for UI broadcasts
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WS Broadcast error: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# Background task to bridge Redis Pub/Sub to WebSockets
async def websocket_bridge():
    # Subscribe to all channels relevant to the UI
    channels = [
        CH_MARKET_DATA, CH_MARKET_REGIME, CH_SIGNALS, 
        CH_AI_JOURNAL, CH_RISK_APPROVED, CH_RISK_REJECTED, 
        CH_EXEC_OPENED, CH_PORTFOLIO_UPDATED, CH_NEWS
    ]
    
    # For a simple bridge, we can spawn a task per channel, or use redis psubscribe
    # To keep it simple, we use the EventBus which currently supports single channel subscribe.
    # We will spawn a task for each channel.
    async def bridge_channel(channel):
        async for msg in event_bus.subscribe(channel):
            await manager.broadcast({
                "type": channel,
                "data": msg
            })
            
    for ch in channels:
        asyncio.create_task(bridge_channel(ch))

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(websocket_bridge())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/metrics")
def get_metrics():
    db = SessionLocal()
    trades = db.query(Trade).all()
    
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t.realized_pnl and t.realized_pnl > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    total_pnl = sum([t.realized_pnl for t in trades if t.realized_pnl])
    
    db.close()
    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "active_positions": len([t for t in trades if str(t.status) == "TradeStatus.OPEN"])
    }

@app.get("/api/trades")
def get_trades():
    db = SessionLocal()
    trades = db.query(Trade).order_by(Trade.opened_at.desc()).limit(50).all()
    result = []
    for t in trades:
        result.append({
            "id": t.id,
            "ticker": t.ticker,
            "action": t.action.name,
            "status": t.status.name,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "realized_pnl": t.realized_pnl,
            "opened_at": t.opened_at
        })
    db.close()
    return result
