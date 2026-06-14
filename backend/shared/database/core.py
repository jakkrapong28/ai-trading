from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:yourpassword@localhost:5432/ai_trading")

# pool_pre_ping avoids stale connections; a small pool covers the to_thread
# workers that now run synchronous queries off the event loop.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_migrations():
    """Lightweight additive migrations for columns that `create_all` won't add
    to already-existing tables. Idempotent — safe to run on every startup.

    Prevents the 'column does not exist' 500s described in README when the live
    DB predates a new model column (e.g. trades.fee).
    """
    from sqlalchemy import text
    statements = [
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS fee DOUBLE PRECISION DEFAULT 0",
        "ALTER TABLE trades ADD COLUMN IF NOT EXISTS trailing_notified BOOLEAN DEFAULT FALSE",
    ]
    try:
        with engine.begin() as conn:
            for stmt in statements:
                conn.execute(text(stmt))
    except Exception as e:
        import logging
        logging.getLogger("db-migrations").warning(f"Schema migration skipped/failed: {e}")


async def run_db(fn, *args):
    """Run a synchronous DB function off the event loop.

    `fn` receives a fresh Session as its first argument and must not retain it.
    Use from async handlers/loops to avoid blocking on synchronous SQLAlchemy.
    """
    def _call():
        db = SessionLocal()
        try:
            return fn(db, *args)
        finally:
            db.close()
    return await asyncio.to_thread(_call)
