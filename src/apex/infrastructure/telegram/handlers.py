
"""Telegram Handlers - Crypto-Only"""
from __future__ import annotations
from telegram import InlineKeyboardMarkup

from ..backtest.telegram_menu import BOT_MENU

async def handle_message(update, context):
    text = update.message.text
    if text:
        menu = BOT_MENU["main"]
        keyboard = InlineKeyboardMarkup(menu["buttons"])
        await update.message.reply_text(menu["text"], reply_markup=keyboard)

async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "live_trading":
        await query.edit_message_text("📊 Live Trading: Active\n10 coins x 14 TFs\nUse /status for details")
    elif data == "market_overview":
        await query.edit_message_text("📈 Market Overview - Top 10 Toobit Coins\n24/7 Crypto Mode")
    elif data == "settings":
        await query.edit_message_text("⚙️ Settings\n• Risk per trade: 1%\n• 13 Evidences\n• No Forex")
    elif data == "positions":
        await query.edit_message_text("📋 Positions: No open positions (demo)")
    elif data == "main":
        menu = BOT_MENU["main"]
        keyboard = InlineKeyboardMarkup(menu["buttons"])
        await query.edit_message_text(menu["text"], reply_markup=keyboard)
