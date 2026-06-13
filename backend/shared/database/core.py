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
