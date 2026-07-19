
from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime

class MessageBuilder:
    """Message Builder per blueprint - No message creation in bot.py"""
    
    @staticmethod
    def main_menu(is_admin: bool = False) -> str:
        admin_badge = "🛡 ADMIN\n" if is_admin else ""
        return f"""━━━━━━━━━━━━━━━━━━
{admin_badge}APEX
Institutional Trading System
━━━━━━━━━━━━━━━━━━

Welcome to APEX Enterprise Control Center.

All operations are available via buttons below.
No typing required.

📊 Backtest - Full history analysis
📈 Trading - Paper & Live
🧠 Optimization - Signal & Risk
📁 Reports - Performance & Export
📡 Market - Real-time overview
💼 Portfolio - Positions & PnL

━━━━━━━━━━━━━━━━━━
Select an option:
"""

    @staticmethod
    def backtest_symbol() -> str:
        return """📊 **Backtest - Select Symbol**

Choose symbol for backtest:
All backtests run on FULL history (Jan 2020 → Now)

No typing - just tap a symbol.
"""

    @staticmethod
    def backtest_timeframe(symbol: str) -> str:
        return f"""📊 **Backtest - {symbol} - Select Timeframe**

Symbol: {symbol}
Data: Full History

Choose timeframe:
"""

    @staticmethod
    def backtest_confirm(symbol: str, timeframe: str, candles: int = 52881) -> str:
        return f"""📊 **Backtest Confirmation**

Symbol: {symbol}
Timeframe: {timeframe}
History: FULL (Jan 2020 → Now)
Candles: ~{candles:,}
Engine: Full APEX pipeline

▶ Ready to run?

This may take 1-5 minutes depending on history.
"""

    @staticmethod
    def backtest_progress(percent: int, stage: str, candles: int = 0, signals: int = 0, elapsed: str = "00:00") -> str:
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
        return f"""⏳ **Running Backtest...**

{bar} {percent}%

Stage: {stage}
Candles: {candles:,}
Signals: {signals:,}
Elapsed: {elapsed}

Please wait - message will update...
"""

    @staticmethod
    def backtest_result(metrics: Dict[str, Any], symbol: str, timeframe: str) -> str:
        return f"""✅ **Backtest Complete - {symbol} {timeframe}**

📊 **Summary:**
• Net Profit: {metrics.get('net_profit', 0):.2f}
• Win Rate: {metrics.get('win_rate', 0):.1%}
• Profit Factor: {metrics.get('profit_factor', 0):.2f}
• Sharpe: {metrics.get('sharpe', 0):.2f}
• Sortino: {metrics.get('sortino', 0):.2f}
• Max DD: {metrics.get('max_dd', 0):.1%}
• Trades: {metrics.get('trades', 0)}
• Expectancy: {metrics.get('expectancy', 0):.4f}
• Avg RR: {metrics.get('avg_rr', 0):.2f}

💡 Next: View signals, charts, AI analysis or run optimization.
"""

    @staticmethod
    def trading_menu() -> str:
        return """📈 **Trading**

Choose mode:

🧪 **Paper Trading** - No real money, full engine simulation
💰 **Live Trading** - Real money, requires confirmation

⚠️ Live Trading uses real funds. Double confirmation required.
"""

    @staticmethod
    def live_warning() -> str:
        return """⚠️ **LIVE TRADING WARNING**

This uses REAL MONEY.
All orders will be sent to Toobit exchange.

• Real balance will be used
• Real fees will apply
• Real risk

Continue to Live Trading?

Tap YES to proceed, NO to cancel.
"""

    @staticmethod
    def optimization_menu() -> str:
        return """🧠 **Optimization Center**

Enterprise optimizer management:

▶ **Run Optimization** - Wizard for new optimization
📋 **Running Jobs** - Queue & active jobs
📚 **Version Manager** - All versions, comparison
📈 **Reports** - Validation & metrics
🧪 **Validation** - WalkForward, MonteCarlo, Stress
📦 **Artifacts** - Parameters, metrics, history
🔄 **Rollback** - Restore previous version

Only Admin can run/rollback. All users can view reports.

Isolation: Never Mix Coins/Timeframes ✅ Enforced
"""

    @staticmethod
    def portfolio_summary(balance: float = 0, equity: float = 0, pnl: float = 0, positions: int = 0) -> str:
        return f"""💼 **Portfolio Summary**

💰 Balance: ${balance:.2f}
📈 Equity: ${equity:.2f}
💹 PnL: ${pnl:.2f} ({pnl/balance*100:.1f}%) if balance>0 else 0
📊 Open Positions: {positions}

View details below.
"""

    @staticmethod
    def status_message(system_status: Dict[str, Any]) -> str:
        return f"""ℹ️ **APEX System Status**

🟢 **Core:**
• Engine: {system_status.get('engine', 'Running')}
• WebSocket: {system_status.get('ws', 'Connected')}
• Exchange: {system_status.get('exchange', 'Online')}

📊 **Trading:**
• Paper: {system_status.get('paper', 'Stopped')}
• Live: {system_status.get('live', 'Stopped')}
• Positions: {system_status.get('positions', 0)}

🧠 **Optimization:**
• Queue: {system_status.get('opt_queue', 0)}
• Running: {system_status.get('opt_running', 0)}
• Versions: {system_status.get('opt_versions', 0)}

❤️ Health: {system_status.get('health', '100%')}
"""

    @staticmethod
    def error_message(error: str, friendly: str = "An error occurred") -> str:
        return f"""❌ **Error**

{friendly}

Details: {error[:200]}

Please try again or contact admin.
Use ⬅ Back or 🏠 Home to continue.
"""

    @staticmethod
    def permission_denied(required_role: str = "Admin") -> str:
        return f"""🔒 **Permission Denied**

This action requires **{required_role}** role.

Your current role does not allow this operation.
Contact owner to upgrade your access.

Use 🏠 Home to return.
"""

    @staticmethod
    def confirmation_required(action: str, details: str = "") -> str:
        return f"""⚠️ **Confirmation Required**

Action: {action}
{details}

This is a sensitive operation.
Are you sure you want to proceed?

Tap YES to confirm, NO to cancel.
"""
