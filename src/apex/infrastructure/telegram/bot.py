
"""Telegram Bot - Crypto-Only - 10 coins x 14 TFs + Backtest Menu"""
from __future__ import annotations
import asyncio
import os
from typing import Dict
from .handlers import handle_message, handle_callback

try:
    from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

from ..backtest.telegram_menu import BOT_MENU, generate_backtest_symbol_menu, generate_timeframe_menu, handle_backtest_callback
from ..backtest.backtest_engine import TOP_10_SYMBOLS, ALL_14_TFS

class ApexTelegramBot:
    def __init__(self, token: str, crypto_app):
        self.token = token
        self.crypto_app = crypto_app
        self.app = None
        
    async def start(self):
        if not HAS_TELEGRAM:
            print("python-telegram-bot not installed")
            return
        
        self.app = Application.builder().token(self.token).build()
        
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("backtest", self.cmd_backtest))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CallbackQueryHandler(self.on_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        await self.app.initialize()
        await self.app.start()
        print("Telegram bot started - Crypto-Only Menu")
        
    async def cmd_start(self, update, context):
        menu = BOT_MENU["main"]
        keyboard = InlineKeyboardMarkup(menu["buttons"])
        await update.message.reply_text(menu["text"], reply_markup=keyboard)
    
    async def cmd_backtest(self, update, context):
        buttons = generate_backtest_symbol_menu()
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("🔬 Select Symbol for FULL HISTORY Backtest (10 coins):", reply_markup=keyboard)
    
    async def cmd_status(self, update, context):
        text = f"""
📊 APEX Status - Crypto-Only
• Symbols: {len(TOP_10_SYMBOLS)} ({', '.join([s.replace('-SWAP-USDT','') for s in TOP_10_SYMBOLS[:5]])}...)
• Timeframes: {len(ALL_14_TFS)} ({', '.join(ALL_14_TFS)})
• Mode: 24/7 (No Forex)
• Evidences: 13 Institutional
"""
        await update.message.reply_text(text)
    
    async def on_callback(self, update, context):
        query = update.callback_query
        await query.answer()
        data = query.data
        
        # Handle backtest menu
        if data in ["main", "backtest_menu"] or data.startswith("bt_"):
            result = await handle_backtest_callback(data, toobit_client=self.crypto_app.execution_engine.adapter if hasattr(self.crypto_app.execution_engine, 'adapter') else None, bot=context.bot, chat_id=query.message.chat_id)
            
            if isinstance(result, dict):
                buttons = result.get("buttons", [])
                keyboard = InlineKeyboardMarkup(buttons) if buttons else None
                text = result.get("text", "Menu")
                
                # If full report exists, send as file
                if "full_report" in result:
                    await query.edit_message_text(text, reply_markup=keyboard)
                    # Send full report as file
                    report = result["full_report"]
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=report.encode(),
                        filename=f"backtest_{result.get('result').symbol}_{result.get('result').timeframe}.txt" if result.get('result') else "backtest_report.txt",
                        caption="📄 Full Institutional Report (Full History, Last 25 Signals)"
                    )
                else:
                    await query.edit_message_text(text, reply_markup=keyboard)
            return
        
        await handle_callback(update, context)
