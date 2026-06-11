from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BrokerAdapter(ABC):
    """
    Abstract base class for all broker integrations (Paper, Simulation, Live)
    """

    @abstractmethod
    async def place_order(self, ticker: str, action: str, lot_size: float, stop_loss: float, take_profit: float, entry_price: float = None) -> Dict[str, Any]:
        """
        Place a new order.
        Returns a dictionary containing broker-specific order details.
        """
        pass

    @abstractmethod
    async def close_order(self, order_id: str, exit_price: float = None) -> Dict[str, Any]:
        """
        Close an existing order.
        Returns a dictionary containing execution details.
        """
        pass

    @abstractmethod
    async def modify_order(self, order_id: str, stop_loss: float = None, take_profit: float = None) -> Dict[str, Any]:
        """
        Modify an existing order's SL/TP.
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Retrieve all active positions from the broker.
        """
        pass
