import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import create_mock_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    # Mock commit, rollback, add, query
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.add = MagicMock()
    session.query = MagicMock()
    return session

@pytest.fixture
def mock_event_bus():
    eb = MagicMock()
    eb.publish = AsyncMock()
    eb.subscribe_group = AsyncMock()
    eb.redis = AsyncMock()
    return eb
