"""Core interfaces for system abstraction."""
from __future__ import annotations

from typing import Protocol
from ..domain.trading import TradeBlueprint, Position

class IExchangeAdapter(Protocol):
    """Exchange abstraction interface (Book II, 3.5)."""

    async def place_order(self, blueprint: TradeBlueprint) -> dict:
        """Submit a new order to the exchange and return raw response."""
        ...

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an existing order."""
        ...

    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Query the status of an order."""
        ...
