
from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    # Mock for testing
    class InlineKeyboardButton:
        def __init__(self, text, callback_data=None, url=None):
            self.text = text
            self.callback_data = callback_data
            self.url = url
        def to_dict(self):
            return {"text": self.text, "callback_data": self.callback_data}
    class InlineKeyboardMarkup:
        def __init__(self, inline_keyboard):
            self.inline_keyboard = inline_keyboard

class KeyboardBuilder:
    """Keyboard Builder per blueprint - Unified, No Duplicate"""
    
    @staticmethod
    def build(buttons: List[List[Dict[str, str]]], add_nav: bool = True, current_menu: str = "main") -> Any:
        """Build keyboard from dict structure"""
        keyboard = []
        for row in buttons:
            kb_row = []
            for btn in row:
                if isinstance(btn, dict):
                    text = btn.get('text', 'Button')
                    cb = btn.get('callback', btn.get('callback_data', 'main'))
                    kb_row.append(InlineKeyboardButton(text=text, callback_data=cb))
                elif isinstance(btn, tuple):
                    kb_row.append(InlineKeyboardButton(text=btn[0], callback_data=btn[1]))
            if kb_row:
                keyboard.append(kb_row)
        
        if add_nav:
            nav_row = KeyboardBuilder.nav_buttons(current_menu)
            if nav_row:
                keyboard.append(nav_row)
        
        return InlineKeyboardMarkup(keyboard) if HAS_TELEGRAM else {"inline_keyboard": [[b.to_dict() if hasattr(b, 'to_dict') else b for b in row] for row in keyboard]}
    
    @staticmethod
    def nav_buttons(current_menu: str = "main") -> List[Any]:
        """Global nav buttons per blueprint: Back, Home, Refresh, Cancel"""
        buttons = []
        if current_menu != "main":
            buttons.append(InlineKeyboardButton("⬅ Back", callback_data="nav.back"))
            buttons.append(InlineKeyboardButton("🏠 Home", callback_data="main"))
        buttons.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"{current_menu}.refresh"))
        return buttons
    
    @staticmethod
    def main_menu(is_admin: bool = False, is_owner: bool = False) -> Any:
        buttons = [
            [{"text": "📊 Backtest", "callback": "backtest.menu"}, {"text": "📈 Trading", "callback": "trading.menu"}],
            [{"text": "🧠 Optimization", "callback": "optimization.menu"}, {"text": "📁 Reports", "callback": "reports.menu"}],
            [{"text": "📡 Market", "callback": "market.menu"}, {"text": "💼 Portfolio", "callback": "portfolio.menu"}],
            [{"text": "⚙ Settings", "callback": "settings.menu"}, {"text": "❤️ Health", "callback": "health.menu"}],
            [{"text": "ℹ Status", "callback": "status.menu"}, {"text": "❓ Help", "callback": "help.menu"}],
        ]
        if is_admin or is_owner:
            buttons.append([{"text": "🛡 ADMIN PANEL", "callback": "admin.menu"}])
        
        return KeyboardBuilder.build(buttons, add_nav=False)
    
    @staticmethod
    def symbol_keyboard(prefix: str = "backtest.symbol") -> Any:
        symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT"]
        buttons = []
        row = []
        for i, sym in enumerate(symbols):
            row.append({"text": sym, "callback": f"{prefix}.{sym}"})
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        return KeyboardBuilder.build(buttons, current_menu="backtest")
    
    @staticmethod
    def timeframe_keyboard(prefix: str = "backtest.tf") -> Any:
        timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1D", "1W"]
        buttons = []
        row = []
        for tf in timeframes:
            row.append({"text": tf, "callback": f"{prefix}.{tf}"})
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        return KeyboardBuilder.build(buttons, current_menu="backtest_timeframe")
    
    @staticmethod
    def confirmation_keyboard(confirm_callback: str, cancel_callback: str = "nav.back", confirm_text: str = "✅ YES", cancel_text: str = "❌ NO") -> Any:
        buttons = [
            [{"text": confirm_text, "callback": confirm_callback}, {"text": cancel_text, "callback": cancel_callback}]
        ]
        return KeyboardBuilder.build(buttons, add_nav=False)
    
    @staticmethod
    def optimization_type_keyboard() -> Any:
        buttons = [
            [{"text": "📡 Signal", "callback": "optimization.type.signal"}, {"text": "🛡 Risk", "callback": "optimization.type.risk"}],
            [{"text": "💼 Portfolio", "callback": "optimization.type.portfolio"}, {"text": "🔗 Full", "callback": "optimization.type.full"}],
        ]
        return KeyboardBuilder.build(buttons, current_menu="optimization_type")
    
    @staticmethod
    def trials_keyboard() -> Any:
        buttons = [
            [{"text": "50", "callback": "optimization.trials.50"}, {"text": "100", "callback": "optimization.trials.100"}, {"text": "200", "callback": "optimization.trials.200"}],
            [{"text": "500", "callback": "optimization.trials.500"}, {"text": "1000", "callback": "optimization.trials.1000"}],
        ]
        return KeyboardBuilder.build(buttons, current_menu="optimization_trials")
    
    @staticmethod
    def pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> Any:
        buttons = []
        row = []
        if current_page > 1:
            row.append({"text": "⬅ Prev", "callback": f"{prefix}.page.{current_page-1}"})
        row.append({"text": f"{current_page}/{total_pages}", "callback": "noop"})
        if current_page < total_pages:
            row.append({"text": "Next ➡", "callback": f"{prefix}.page.{current_page+1}"})
        buttons.append(row)
        return buttons
