
from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio, logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

class NotificationService:
    """Notification Engine per blueprint - Event Driven"""
    
    def __init__(self, bot=None):
        self.bot = bot
        self.subscribers: Dict[str, List[int]] = {}  # event_type -> [chat_ids]
        self.enabled = True
    
    def subscribe(self, user_id: int, event_type: str = "all"):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if user_id not in self.subscribers[event_type]:
            self.subscribers[event_type].append(user_id)
    
    def unsubscribe(self, user_id: int, event_type: str = "all"):
        if event_type in self.subscribers and user_id in self.subscribers[event_type]:
            self.subscribers[event_type].remove(user_id)
    
    async def notify(self, event_type: str, message: str, chat_ids: List[int] = None, priority: str = "normal"):
        if not self.enabled:
            return
        
        targets = chat_ids or self.subscribers.get(event_type, []) + self.subscribers.get("all", [])
        targets = list(set(targets))  # Deduplicate
        
        if not targets or not self.bot:
            log.info(f"Notification [{event_type}]: {message[:100]} - No subscribers or bot not set")
            return
        
        for chat_id in targets:
            try:
                if self.bot:
                    await self.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')
                log.info(f"Notified {chat_id} about {event_type}")
            except Exception as e:
                log.error(f"Failed to notify {chat_id}: {e}")
    
    async def notify_order_filled(self, order: Dict[str, Any], chat_id: int):
        msg = f"""✅ **Order Filled**

Symbol: {order.get('symbol')}
Side: {order.get('side')}
Price: {order.get('price')}
Qty: {order.get('qty')}
"""
        await self.notify("order.filled", msg, [chat_id], priority="high")
    
    async def notify_position_closed(self, position: Dict[str, Any], chat_id: int):
        pnl = position.get('pnl', 0)
        emoji = "🟢" if pnl > 0 else "🔴"
        msg = f"""{emoji} **Position Closed**

Symbol: {position.get('symbol')}
PnL: {pnl:+.2f} ({position.get('pnl_percent',0):+.1f}%)
Reason: {position.get('reason','')}
"""
        await self.notify("position.closed", msg, [chat_id], priority="high")
    
    async def notify_optimization_complete(self, package: Any, chat_id: int):
        msg = f"""🎉 **Optimization Complete**

Symbol: {package.symbol}
TF: {package.timeframe}
Type: {package.optimizer_type.value if hasattr(package.optimizer_type, 'value') else package.optimizer_type}
Score: {package.validation_results.get('composite_score',0):.3f}
Status: {package.status}

Use /opt_report to view details.
"""
        await self.notify("optimization.complete", msg, [chat_id], priority="normal")
    
    async def notify_drawdown_warning(self, drawdown: float, chat_id: int):
        msg = f"""⚠️ **Drawdown Warning**

Current DD: {drawdown:.1%}
Threshold exceeded!

Consider reducing risk or pausing trading.
"""
        await self.notify("risk.drawdown", msg, [chat_id], priority="high")
    
    async def notify_emergency(self, message: str, chat_ids: List[int]):
        await self.notify("emergency", f"🚨 **EMERGENCY**\n\n{message}", chat_ids, priority="critical")
