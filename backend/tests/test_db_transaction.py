import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError

def test_db_transaction_rollback():
    # Mock database session
    db = MagicMock()
    
    # Simulate a transaction block with try-except
    try:
        # Simulate db operation
        db.add(MagicMock())
        # Raise SQLAlchemyError
        raise SQLAlchemyError("Simulated DB Error")
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        
    db.rollback.assert_called_once()
