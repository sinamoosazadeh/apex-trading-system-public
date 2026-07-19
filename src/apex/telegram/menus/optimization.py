
from __future__ import annotations
from ..utils.keyboard_builder import KeyboardBuilder
from ..utils.message_builder import MessageBuilder

class OptimizationMenu:
    @staticmethod
    def main_menu():
        return {
            "message": MessageBuilder.optimization_menu(),
            "keyboard": KeyboardBuilder.build([
                [{"text": "▶ Run Optimization", "callback": "optimization.run.menu"}],
                [{"text": "📋 Running Jobs", "callback": "optimization.jobs"}, {"text": "📚 Versions", "callback": "optimization.versions"}],
                [{"text": "📈 Reports", "callback": "optimization.reports"}, {"text": "📦 Artifacts", "callback": "optimization.artifacts"}],
                [{"text": "🔄 Rollback", "callback": "optimization.rollback.menu"}],
            ], current_menu="optimization")
        }
    
    @staticmethod
    def symbol_menu():
        return {
            "message": "🧠 **Optimization - Select Symbol**\n\nChoose symbol to optimize:",
            "keyboard": KeyboardBuilder.symbol_keyboard("optimization.symbol")
        }
    
    @staticmethod
    def timeframe_menu(symbol: str):
        return {
            "message": f"🧠 **Optimization - {symbol} - Select Timeframe**",
            "keyboard": KeyboardBuilder.timeframe_keyboard(f"optimization.tf.{symbol}")
        }
    
    @staticmethod
    def type_menu(symbol: str, timeframe: str):
        return {
            "message": f"🧠 **Optimization - {symbol} {timeframe} - Select Type**\n\n○ Signal - Evidence weights, thresholds\n○ Risk - SL/TP, sizing, portfolio",
            "keyboard": KeyboardBuilder.optimization_type_keyboard()
        }
    
    @staticmethod
    def trials_menu(symbol: str, timeframe: str, opt_type: str):
        return {
            "message": f"🧠 **Optimization - {symbol} {timeframe} {opt_type} - Trials**\n\nSelect number of trials:",
            "keyboard": KeyboardBuilder.trials_keyboard()
        }
    
    @staticmethod
    def confirm_menu(symbol: str, timeframe: str, opt_type: str, trials: int):
        from ..utils.keyboard_builder import InlineKeyboardButton
        try:
            from telegram import InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton(f"▶ Start {trials} Trials", callback_data=f"optimization.start.{symbol}.{timeframe}.{opt_type}.{trials}")],
                [InlineKeyboardButton("⬅ Back", callback_data="optimization.menu"), InlineKeyboardButton("🏠 Home", callback_data="main")]
            ]
            kb = InlineKeyboardMarkup(keyboard)
        except:
            kb = None
        
        return {
            "message": f"""🧠 **Optimization Confirmation**

Symbol: {symbol}
Timeframe: {timeframe}
Type: {opt_type}
Trials: {trials}

Validation: WalkForward + MonteCarlo + Stress + Robustness
Estimated Time: {trials * 2} sec
Isolation: Never Mix Coins/Timeframes ✅

Run optimization?
""",
            "keyboard": kb
        }
