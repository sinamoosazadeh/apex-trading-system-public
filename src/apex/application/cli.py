
"""CLI - Crypto-Only - 10 coins x 14 TFs + Backtest"""
from __future__ import annotations
import asyncio
import argparse
import os
from .bootstrap import CryptoApplication
from ..backtest.backtest_engine import TOP_10_SYMBOLS, ALL_14_TFS

def main() -> None:
    parser = argparse.ArgumentParser(description="APEX Crypto Trading - 10 coins x 14 TFs - No Forex")
    parser.add_argument("--api-key", default=os.getenv("TOOBIT_API_KEY"))
    parser.add_argument("--api-secret", default=os.getenv("TOOBIT_API_SECRET"))
    parser.add_argument("--symbol", "-s", action="append", help="Trading symbol (default: 10 top coins)")
    parser.add_argument("--timeframe", "-t", default="1h", help=f"Timeframe {ALL_14_TFS}")
    parser.add_argument("--capital", "-c", type=float, default=10000.0)
    parser.add_argument("--backtest", action="store_true", help="Run full history backtest")
    parser.add_argument("--backtest-symbol", help="Symbol for backtest")
    parser.add_argument("--backtest-tf", help="Timeframe for backtest")
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram bot token")
    
    args = parser.parse_args()
    
    symbols = args.symbol if args.symbol else TOP_10_SYMBOLS
    
    if args.backtest:
        # Run backtest mode
        async def run_bt():
            from ..backtest.backtest_engine import InstitutionalBacktestEngine
            import json
            # Load bars from file or API
            print(f"Running FULL HISTORY backtest for {args.backtest_symbol} {args.backtest_tf}")
            # Placeholder for real data fetch
            print("Use Telegram bot /backtest for full functionality")
        
        asyncio.run(run_bt())
        return
    
    if not args.api_key or not args.api_secret:
        print("Error: TOOBIT_API_KEY and TOOBIT_API_SECRET required")
        return

    app = CryptoApplication(api_key=args.api_key, api_secret=args.api_secret, symbols=symbols, initial_capital=args.capital)
    
    # Start telegram bot if token provided
    if args.telegram_token:
        from ..infrastructure.telegram.bot import ApexTelegramBot
        async def run_with_bot():
            bot = ApexTelegramBot(args.telegram_token, app)
            await bot.start()
            await app.run()
        asyncio.run(run_with_bot())
    else:
        asyncio.run(app.run())

if __name__ == "__main__":
    main()
