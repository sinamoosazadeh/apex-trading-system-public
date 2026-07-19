"""Telegram Bot Interface - 14 TFs, Navigation, Enhanced Emojis, Multi-TF In-time."""
from __future__ import annotations
import asyncio
import logging
from typing import List, TYPE_CHECKING
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application as TGApplication, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import Conflict, NetworkError, TimedOut

if TYPE_CHECKING:
    from ..application.bootstrap import Application

log = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, app: "Application"):
        self.app = app
        self.token = app.tg_token
        self.chat_id = app.tg_chat_id
        self.tg_app = TGApplication.builder().token(self.token).read_timeout(60).write_timeout(60).connect_timeout(60).pool_timeout(60).build()
        self.tg_app.add_handler(CommandHandler("start", self.start))
        self.tg_app.add_handler(CallbackQueryHandler(self.button_handler))
        self.symbols: List[str] = []
        self.timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "1w", "1M"]

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [InlineKeyboardButton("📊 Backtest (Full History)", callback_data="menu_backtest")],
            [InlineKeyboardButton("⚡ In-time Trade (All TFs)", callback_data="menu_intime")]
        ]
        await update.message.reply_text("APEX Trading System Control Panel:\nSelect an option:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        
        if data == "menu_backtest" or data == "menu_intime":
            await self._show_symbols(query, data)
        elif data.startswith("backtest_symbol_"):
            symbol = data.replace("backtest_symbol_", "")
            await self._show_timeframes(query, f"backtest_tf_{symbol}_")
        elif data.startswith("backtest_tf_"):
            parts = data.replace("backtest_tf_", "").split("_")
            symbol, tf = parts[0], parts[1]
            await query.edit_message_text(f"Running FULL HISTORY backtest for {symbol} on {tf}...\nPlease wait.")
            asyncio.create_task(self._run_backtest(query, symbol, tf))
        elif data.startswith("intime_symbol_"):
            symbol = data.replace("intime_symbol_", "")
            await self._show_modes(query, f"intime_mode_{symbol}_")
        elif data.startswith("intime_mode_"):
            parts = data.replace("intime_mode_", "").split("_")
            symbol, mode = parts[0], parts[1]
            self.app.mode = mode.upper()
            await query.edit_message_text(f"Starting In-time Trade for {symbol} on ALL timeframes in {self.app.mode} mode...")
            await self._run_intime(query, symbol)
        elif data == "back_to_main":
            await self.start(update, context)
        elif data == "back_to_symbols_bt":
            await self._show_symbols(query, "menu_backtest")
        elif data == "back_to_symbols_it":
            await self._show_symbols(query, "menu_intime")

    async def _show_symbols(self, query, menu_type: str) -> None:
        if not self.symbols:
            await query.edit_message_text("Fetching top 10 symbols...")
            self.symbols = await self.app.toobit_adapter.client.get_top_volume_symbols(10)
        
        keyboard = [[InlineKeyboardButton(s, callback_data=f"{menu_type.replace('menu_', '')}_symbol_{s}")] for s in self.symbols]
        keyboard.append([InlineKeyboardButton("↩️ Back to Main Menu", callback_data="back_to_main")])
        await query.edit_message_text("Select Symbol:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _show_timeframes(self, query, prefix: str) -> None:
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"{prefix}{tf}")] for tf in self.timeframes]
        keyboard.append([InlineKeyboardButton("↩️ Back to Symbols", callback_data="back_to_symbols_bt")])
        await query.edit_message_text("Select Timeframe:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _show_modes(self, query, prefix: str) -> None:
        keyboard = [
            [InlineKeyboardButton("📄 Paper (Signal Only)", callback_data=f"{prefix}paper")],
            [InlineKeyboardButton("🟢 Live (Execute Trade)", callback_data=f"{prefix}live")],
            [InlineKeyboardButton("↩️ Back to Symbols", callback_data="back_to_symbols_it")]
        ]
        await query.edit_message_text("Select Mode:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def _run_backtest(self, query, symbol: str, tf: str) -> None:
        from ..research.backtest_engine import BacktestEngine
        bt_engine = BacktestEngine(self.app.kernel, self.app.toobit_adapter)
        result = await bt_engine.run_backtest(symbol, tf)
        
        if "error" in result:
            await query.message.reply_text(f"Error: {result['error']}")
            return
        
        signals = result.get("signals_for_display", [])
        total_sigs = result.get("total_signals_generated", 0)
        if signals:
            await query.message.reply_text(f"📋 *Last {len(signals)} Signals (out of {total_sigs}):*", parse_mode="Markdown")
            for i, sig in enumerate(signals, 1):
                await query.message.reply_text(f"{i}. {sig}", parse_mode="Markdown")
                await asyncio.sleep(0.3)
        else:
            await query.message.reply_text("No signals generated.")
            
        m = result["metrics"]
        msg = (
            f"📊 *Full History Backtest Results*\n"
            f"Symbol: `{result['symbol']}` | TF: `{result['timeframe']}`\n"
            f"Candles: `{result['total_bars']}`\n"
            f"-------------------\n"
            f"*Trades:* {m['total_trades']} (L: {m['long_trades']} / S: {m['short_trades']})\n"
            f"*Wins:* {m['wins']} (L: {m['long_wins']} / S: {m['short_wins']})\n"
            f"*Losses:* {m['losses']}\n"
            f"*Win Rate:* `{m['win_rate']:.2f}%`\n"
            f"*Net PNL:* `{m['net_pnl']:.2f} USDT`\n"
            f"*Net Profit:* `{m['net_profit_pct']:.2f}%`\n"
            f"*Profit Factor:* `{m['profit_factor']:.2f}`\n"
            f"*Max Drawdown:* `{m['max_drawdown']:.2f}%`\n"
            f"*Consec W/L:* {m['max_consec_wins']} / {m['max_consec_losses']}\n"
            f"*Sharpe Ratio:* `{m['sharpe']:.2f}`"
        )
        await query.message.reply_text(msg, parse_mode="Markdown")

    async def _run_intime(self, query, symbol: str) -> None:
        self.app.mode = self.app.mode.upper()
        self.app.active_intime_symbol = symbol
        self.app.active_intime_tf = "ALL"  # Monitor all TFs
        
        if symbol not in self.app.ws_client.symbols:
            self.app.ws_client.symbols.append(symbol)
            import json
            if self.app.ws_client._ws:
                # Subscribe to Trades
                sub_msg = {"symbol": symbol, "topic": "trade", "event": "sub", "params": {"binary": "false"}}
                await self.app.ws_client._ws.send(json.dumps(sub_msg))
                
                # Subscribe to ALL 14 Timeframes
                for tf_str in self.timeframes:
                    sub_msg = {"symbol": symbol, "topic": f"kline_{tf_str}", "event": "sub", "params": {"binary": "false"}}
                    await self.app.ws_client._ws.send(json.dumps(sub_msg))
                    await asyncio.sleep(0.1)
                    
        await query.message.reply_text(f"✅ In-time trade started for {symbol} on ALL timeframes (1m to 1M) in {self.app.mode} mode.")

    async def send_signal(self, msg: str) -> None:
        try:
            await self.tg_app.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            log.error(f"Failed to send TG message: {e}")

    async def run(self) -> None:
        log.info("Initializing Telegram Bot...")
        retry_delay = 2.0
        while self.app._running:
            try:
                await self.tg_app.initialize()
                await self.tg_app.bot.delete_webhook(drop_pending_updates=True)
                await self.tg_app.start()
                await self.tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
                log.info("Telegram Bot started successfully.")
                retry_delay = 2.0
                while self.app._running: await asyncio.sleep(1)
            except (NetworkError, TimedOut) as e:
                log.warning(f"TG Network Error: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60.0)
            except Conflict as e:
                log.error(f"TG Conflict: {e.message}")
                break
            except Exception as e:
                log.error(f"TG unexpected error: {e}")
                await asyncio.sleep(5.0)
            finally:
                try:
                    await self.tg_app.updater.stop()
                    await self.tg_app.stop()
                    await self.tg_app.shutdown()
                except: pass
