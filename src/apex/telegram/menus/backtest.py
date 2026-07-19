
from __future__ import annotations
from ..utils.keyboard_builder import KeyboardBuilder
from ..utils.message_builder import MessageBuilder

class BacktestMenu:
    @staticmethod
    def symbol_menu():
        return {
            "message": MessageBuilder.backtest_symbol(),
            "keyboard": KeyboardBuilder.symbol_keyboard("backtest.symbol")
        }
    
    @staticmethod
    def timeframe_menu(symbol: str):
        return {
            "message": MessageBuilder.backtest_timeframe(symbol),
            "keyboard": KeyboardBuilder.timeframe_keyboard(f"backtest.tf.{symbol}")
        }
    
    @staticmethod
    def confirm_menu(symbol: str, timeframe: str):
        from ..utils.keyboard_builder import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("▶ Run Backtest", callback_data=f"backtest.run.{symbol}.{timeframe}")],
            [InlineKeyboardButton("⬅ Back", callback_data="backtest.menu"), InlineKeyboardButton("🏠 Home", callback_data="main")]
        ]
        try:
            from telegram import InlineKeyboardMarkup as TGMarkup
            kb = TGMarkup(keyboard)
        except:
            kb = keyboard
        return {
            "message": MessageBuilder.backtest_confirm(symbol, timeframe),
            "keyboard": kb
        }
    
    @staticmethod
    def result_menu(symbol: str, timeframe: str, metrics: dict):
        from ..utils.keyboard_builder import InlineKeyboardButton
        try:
            from telegram import InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("📈 Equity", callback_data=f"backtest.chart.equity.{symbol}.{timeframe}"),
                 InlineKeyboardButton("📉 Drawdown", callback_data=f"backtest.chart.dd.{symbol}.{timeframe}")],
                [InlineKeyboardButton("📊 Stats", callback_data=f"backtest.stats.{symbol}.{timeframe}"),
                 InlineKeyboardButton("🧠 AI Analysis", callback_data=f"backtest.ai.{symbol}.{timeframe}")],
                [InlineKeyboardButton("🧠 Optimize", callback_data=f"optimization.run.{symbol}.{timeframe}"),
                 InlineKeyboardButton("📤 Export", callback_data=f"backtest.export.{symbol}.{timeframe}")],
                [InlineKeyboardButton("⬅ Back", callback_data="backtest.menu"), InlineKeyboardButton("🏠 Home", callback_data="main")]
            ]
            kb = InlineKeyboardMarkup(keyboard)
        except:
            kb = None
        
        return {
            "message": MessageBuilder.backtest_result(metrics, symbol, timeframe),
            "keyboard": kb
        }
