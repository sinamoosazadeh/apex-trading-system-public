
from __future__ import annotations
from ..utils.keyboard_builder import KeyboardBuilder
from ..utils.message_builder import MessageBuilder

class TradingMenu:
    @staticmethod
    def main_menu():
        return {
            "message": MessageBuilder.trading_menu(),
            "keyboard": KeyboardBuilder.build([
                [{"text": "🧪 Paper Trading", "callback": "trading.paper.menu"}],
                [{"text": "💰 Live Trading", "callback": "trading.live.warning"}],
            ], current_menu="trading")
        }
    
    @staticmethod
    def paper_menu():
        return {
            "message": """🧪 **Paper Trading**

No real money - full engine simulation

▶ Start
■ Stop
📈 Signals
📊 Performance
⚙ Settings
""",
            "keyboard": KeyboardBuilder.build([
                [{"text": "▶ Start", "callback": "trading.paper.start"}, {"text": "■ Stop", "callback": "trading.paper.stop"}],
                [{"text": "📈 Live Signals", "callback": "trading.paper.signals"}, {"text": "📊 Performance", "callback": "trading.paper.performance"}],
            ], current_menu="trading_paper")
        }
    
    @staticmethod
    def live_warning():
        return {
            "message": MessageBuilder.live_warning(),
            "keyboard": KeyboardBuilder.confirmation_keyboard("trading.live.menu", "trading.menu", "✅ YES, Continue", "❌ NO")
        }
    
    @staticmethod
    def live_menu():
        return {
            "message": """💰 **Live Trading - REAL MONEY**

⚠️ Real funds will be used

▶ Start
■ Stop
📈 Open Positions
📋 Orders
💰 Balance
📊 Performance
⚙ Risk
🚨 Emergency

""",
            "keyboard": KeyboardBuilder.build([
                [{"text": "▶ Start Live", "callback": "trading.live.start"}, {"text": "■ Stop Live", "callback": "trading.live.stop"}],
                [{"text": "📈 Positions", "callback": "trading.live.positions"}, {"text": "📋 Orders", "callback": "trading.live.orders"}],
                [{"text": "💰 Balance", "callback": "trading.live.balance"}, {"text": "📊 Performance", "callback": "trading.live.performance"}],
                [{"text": "🚨 Emergency", "callback": "trading.live.emergency"}],
            ], current_menu="trading_live")
        }
    
    @staticmethod
    def emergency_menu():
        return {
            "message": """🚨 **Emergency Center**

⚠️ Dangerous operations - Double confirmation required

Options:
• Pause Trading - Pause new entries
• Close All Positions - Close everything
• Cancel All Orders - Cancel all pending
• Safe Mode - Emergency safe mode
• Disconnect - Disconnect exchange
""",
            "keyboard": KeyboardBuilder.build([
                [{"text": "⏸ Pause", "callback": "trading.live.pause"}, {"text": "▶ Resume", "callback": "trading.live.resume"}],
                [{"text": "❌ Close All Positions", "callback": "trading.live.close_all.confirm"}],
                [{"text": "🚫 Cancel All Orders", "callback": "trading.live.cancel_all.confirm"}],
                [{"text": "🛡 Safe Mode", "callback": "trading.live.safe_mode"}],
            ], current_menu="trading_live_emergency")
        }
