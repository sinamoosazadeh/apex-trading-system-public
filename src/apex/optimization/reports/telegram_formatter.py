"""Telegram formatter for optimization reports"""
class TelegramFormatter:
    def format(self, package): return f"✅ Optimized {package.symbol} {package.timeframe} Score: {package.validation_results.get(\"composite_score\",0):.3f}"
