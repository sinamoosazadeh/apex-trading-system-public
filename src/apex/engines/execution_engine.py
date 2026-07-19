"""Institutional Execution Engine - Manages order lifecycle and retries."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..core.interfaces import IExchangeAdapter
from ..domain.trading import TradeBlueprint

log = logging.getLogger(__name__)

class ExecutionEngine:
    """Orchestrates trade execution against an exchange."""

    def __init__(self, adapter: IExchangeAdapter, max_retries: int = 3) -> None:
        self.adapter = adapter
        self.max_retries = max_retries

    async def execute_blueprint(self, blueprint: TradeBlueprint) -> dict:
        """Execute a trade blueprint and handle retries on transient errors."""
        
        retry_count = 0
        last_response = {}
        
        while retry_count <= self.max_retries:
            log.info(f"Placing order attempt {retry_count + 1} for {blueprint.symbol} {blueprint.direction}")
            
            response = await self.adapter.place_order(blueprint)
            last_response = response
            
            # Check if response indicates success
            if "orderId" in response and response.get("status") in ["NEW", "PARTIALLY_FILLED", "FILLED"]:
                log.info(f"Order {response['orderId']} accepted with status {response['status']}")
                return response
                
            # Check if rejection is transient (e.g., rate limit -1015, timeout -1007)
            error_code = response.get("code", 0)
            if error_code in [-1015, -1007, -1000] and retry_count < self.max_retries:
                log.warning(f"Transient error {error_code}, retrying in 1s...")
                await asyncio.sleep(1.0)
                retry_count += 1
                continue
            else:
                log.error(f"Order permanently rejected: {response.get('msg')}")
                return response

        return last_response

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an active order."""
        return await self.adapter.cancel_order(order_id, symbol)
