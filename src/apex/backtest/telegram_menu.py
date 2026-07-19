
"""Telegram Bot Integration - Backtest Menu - Crypto-Only"""
from __future__ import annotations
import asyncio
from typing import List
from .backtest_engine import InstitutionalBacktestEngine, TOP_10_SYMBOLS, ALL_14_TFS

# Menu Structure per existing bot (preserving structure)
BOT_MENU = {
    "main": {
        "text": "🤖 APEX Crypto Bot - Main Menu\n10 Coins | 14 TFs | 24/7 | No Forex",
        "buttons": [
            [{"text": "📊 Live Trading", "callback_data": "live_trading"}],
            [{"text": "🔬 Backtest (Full History)", "callback_data": "backtest_menu"}],
            [{"text": "📈 Market Overview", "callback_data": "market_overview"}],
            [{"text": "⚙️ Settings", "callback_data": "settings"}],
            [{"text": "📋 Positions", "callback_data": "positions"}]
        ]
    },
    "backtest_menu": {
        "text": "🔬 INSTITUTIONAL BACKTEST\nSelect Symbol (10 Toobit Top Coins):",
        "buttons": []  # Generated dynamically
    }
}

def generate_backtest_symbol_menu():
    buttons = []
    row = []
    for i, symbol in enumerate(TOP_10_SYMBOLS):
        clean = symbol.replace("-SWAP-USDT", "")
        row.append({"text": clean, "callback_data": f"bt_symbol_{symbol}"})
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "⬅️ Back", "callback_data": "main"}])
    return buttons

def generate_timeframe_menu(symbol: str):
    buttons = []
    row = []
    for tf in ALL_14_TFS:
        row.append({"text": tf, "callback_data": f"bt_tf_{symbol}_{tf}"})
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([{"text": "⬅️ Back to Symbols", "callback_data": "backtest_menu"}])
    return buttons

async def handle_backtest_callback(callback_data: str, toobit_client=None, bot=None, chat_id=None):
    """Handle backtest flow: Symbol -> Timeframe -> Full History Backtest -> Report + Last 25 Signals"""
    if callback_data == "backtest_menu":
        menu = BOT_MENU["backtest_menu"].copy()
        menu["buttons"] = generate_backtest_symbol_menu()
        return menu
    
    if callback_data.startswith("bt_symbol_"):
        symbol = callback_data.replace("bt_symbol_", "")
        return {
            "text": f"📊 Selected: {symbol}\nSelect Timeframe (14 TFs - Full History will be tested):",
            "buttons": generate_timeframe_menu(symbol)
        }
    
    if callback_data.startswith("bt_tf_"):
        # Format: bt_tf_SYMBOL_TIMEFRAME - need to parse
        parts = callback_data.replace("bt_tf_", "").split("_")
        # Symbol is like BTC-SWAP-USDT which contains _
        # Actually our symbol is BTC-SWAP-USDT, timeframe is last part
        timeframe = parts[-1]
        symbol = "_".join(parts[:-1])
        if "-SWAP" not in symbol:
            # Reconstruct
            symbol = symbol.replace("-SWAP", "-SWAP-") if "SWAP" in symbol else symbol
        
        # For simplicity, parse correctly: symbol is everything before last _
        # Since we have 14 TFs without _, we can split
        # callback_data = bt_tf_BTC-SWAP-USDT_1m -> symbol=BTC-SWAP-USDT, tf=1m
        raw = callback_data[len("bt_tf_"):]
        # Find last _ before timeframe
        last_us = raw.rfind("_")
        symbol = raw[:last_us]
        timeframe = raw[last_us+1:]
        
        # Send "running" message
        if bot and chat_id:
            await bot.send_message(chat_id, f"⏳ Running FULL HISTORY backtest for {symbol} {timeframe}...\nFetching all candles from Toobit...\nThis may take 1-2 minutes (full history per blueprint)")
        
        # Run backtest
        engine = InstitutionalBacktestEngine()
        
        # Fetch full history from Toobit
        bars = []
        if toobit_client:
            try:
                # Real Toobit REST fetch - full history
                # Using Toobit API: GET /api/v1/market/klines
                # Pagination for full history
                bars = await fetch_toobit_full_history(toobit_client, symbol, timeframe)
            except Exception as e:
                bars = []
        
        if not bars:
            return {
                "text": f"❌ No data for {symbol} {timeframe}. Check Toobit API.",
                "buttons": [[{"text": "⬅️ Back", "callback_data": f"bt_symbol_{symbol}"}]]
            }
        
        result = engine.run_backtest_on_bars(bars, symbol, timeframe)
        report = engine.generate_comprehensive_report(result)
        
        # Split report if too long for Telegram (4096 char limit)
        # Send as file if too long, plus summary
        summary = f"""
✅ BACKTEST COMPLETE - {symbol} {timeframe}

📊 Total Candles: {result.total_candles:,} (FULL HISTORY)
📈 Trades: {result.metrics.total_trades} | Win Rate: {result.metrics.win_rate*100:.1f}%
💰 Total R: {result.metrics.total_r:+.2f}R | PF: {result.metrics.profit_factor:.2f}
📉 Max DD: {result.metrics.max_drawdown_r:.2f}R

Showing last 25 of {len(result.signals)} signals in full report.
"""
        
        # Return both summary and full report
        return {
            "text": summary,
            "full_report": report,  # Will be sent as document
            "buttons": [
                [{"text": "📄 Full Report", "callback_data": f"bt_report_{symbol}_{timeframe}"}],
                [{"text": "🔄 New Backtest", "callback_data": "backtest_menu"}],
                [{"text": "🏠 Main Menu", "callback_data": "main"}]
            ],
            "result": result
        }

async def fetch_toobit_full_history(client, symbol: str, timeframe: str):
    """Fetch FULL history from Toobit - per blueprints, all available candles"""
    import time
    all_bars = []
    # Toobit timeframe mapping
    tf_map = {
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
        "1h": "1h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h",
        "1d": "1d", "3d": "3d", "1w": "1w", "1M": "1M"
    }
    toobit_tf = tf_map.get(timeframe, timeframe)
    
    # Pagination: fetch backwards from now until no more data
    end_time = int(time.time() * 1000)
    limit = 200  # Toobit max per request
    
    while True:
        try:
            klines = await client.get_klines(symbol=symbol, interval=toobit_tf, limit=limit, end_time=end_time)
            if not klines:
                break
            # Convert to MarketBar
            for k in klines:
                bar = MarketBar(
                    timestamp=k[0]/1000 if isinstance(k, list) else k.get('openTime', end_time)/1000,
                    open=float(k[1]) if isinstance(k, list) else float(k.get('open', 0)),
                    high=float(k[2]) if isinstance(k, list) else float(k.get('high', 0)),
                    low=float(k[3]) if isinstance(k, list) else float(k.get('low', 0)),
                    close=float(k[4]) if isinstance(k, list) else float(k.get('close', 0)),
                    volume=float(k[5]) if isinstance(k, list) else float(k.get('volume', 0)),
                    symbol=symbol,
                    timeframe=timeframe
                )
                all_bars.append(bar)
            
            # Move end_time backwards
            if isinstance(klines[0], list):
                earliest = klines[0][0]
            else:
                earliest = klines[0].get('openTime', end_time - limit*60000)
            
            end_time = earliest - 1
            
            if len(klines) < limit:
                break
                
            await asyncio.sleep(0.2)  # Rate limit
            
            # Safety: max 10000 candles per timeframe (full history is usually <10000 for 1M, >100k for 1m)
            if len(all_bars) > 50000:
                break
                
        except Exception as e:
            print(f"Fetch error: {e}")
            break
    
    all_bars.sort(key=lambda x: x.timestamp)
    return all_bars
