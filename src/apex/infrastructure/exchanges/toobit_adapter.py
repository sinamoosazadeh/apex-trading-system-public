"""Toobit Exchange Adapter - Implements IExchangeAdapter."""
from __future__ import annotations

import math
from typing import Any

from ...core.interfaces import IExchangeAdapter
from ...domain.trading import TradeBlueprint
from .toobit_client import ToobitClient, ToobitClientError

class ToobitAdapter(IExchangeAdapter):
    """Adapter for Toobit Exchange."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self.client = ToobitClient(api_key, api_secret)

    def _map_direction_to_side(self, direction: str) -> str:
        """Maps APEX direction to Toobit side (BUY_OPEN / SELL_OPEN)."""
        if direction == "LONG": return "BUY_OPEN"
        elif direction == "SHORT": return "SELL_OPEN"
        raise ValueError(f"Invalid direction for order placement: {direction}")

    async def place_order(self, blueprint: TradeBlueprint) -> dict:
        """Place order on Toobit and return raw response dict."""
        params = {
            "symbol": blueprint.symbol,
            "side": self._map_direction_to_side(blueprint.direction),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(blueprint.position_size),
            "price": str(blueprint.entry_price),
            "priceType": "INPUT",
            "newClientOrderId": blueprint.decision_id
        }
        
        try:
            response = await self.client.place_futures_order(**params)
            return response
        except ToobitClientError as e:
            # Return a standardized error dict instead of raising exception
            return {"code": e.code, "msg": e.msg, "status": "REJECTED"}

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await self.client.cancel_futures_order(symbol, order_id)
            return True
        except ToobitClientError:
            return False

    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        # This would call GET /api/v1/futures/order in a real scenario
        # For simplicity in this phase, we return a mock
        return {"orderId": order_id, "status": "NEW"}
