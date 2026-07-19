import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("TG_TEST")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Backtest", callback_data="test_1")],
        [InlineKeyboardButton("⚡ In-time Trade", callback_data="test_2")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("✅ APEX Bot is ALIVE!\nSelect an option:", reply_markup=reply_markup)
    log.info("Sent /start response to user.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"Selected option: {query.data}")

async def main():
    if not TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set in environment!")
        return

    log.info("Initializing Telegram Bot...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    
    await app.initialize()
    await app.bot.delete_webhook(drop_pending_updates=True)
    
    # Send a proactive message to verify sending capability
    try:
        await app.bot.send_message(chat_id=CHAT_ID, text="🚀 APEX Test Script Started. Send /start to see the menu!")
        log.info("Proactive message sent successfully.")
    except Exception as e:
        log.error(f"Failed to send proactive message: {e}")
        return
        
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    log.info("Polling started. Send /start in Telegram now. Press Ctrl+C to stop.")
    
    await asyncio.Event().wait() # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
