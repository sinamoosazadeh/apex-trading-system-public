"""Command-line interface for APEX."""
from __future__ import annotations
import asyncio
import argparse
import os
from .bootstrap import Application

def main() -> None:
    parser = argparse.ArgumentParser(description="APEX Trading Intelligence Platform")
    parser.add_argument("--api-key", default=os.getenv("TOOBIT_API_KEY"), help="Toobit API Key")
    parser.add_argument("--api-secret", default=os.getenv("TOOBIT_API_SECRET"), help="Toobit API Secret")
    parser.add_argument("--capital", "-c", type=float, default=10000.0, help="Initial capital (USDT)")
    
    args = parser.parse_args()
    
    if not args.api_key or not args.api_secret:
        print("Error: TOOBIT_API_KEY and TOOBIT_API_SECRET must be provided.")
        return

    app = Application(
        api_key=args.api_key,
        api_secret=args.api_secret,
        symbols=[],  # خالی، زیرا منتظر تلگرام می‌مانیم
        initial_capital=args.capital
    )
    asyncio.run(app.run())

if __name__ == "__main__":
    main()
