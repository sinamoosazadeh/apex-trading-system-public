
from __future__ import annotations
from typing import Dict, Any, List

class PortfolioFormatter:
    @staticmethod
    def format_summary(portfolio: Dict[str, Any]) -> str:
        return f"""💼 **Portfolio Summary**

💰 Balance: ${portfolio.get('balance',0):.2f}
📈 Equity: ${portfolio.get('equity',0):.2f}
💹 PnL: ${portfolio.get('pnl',0):.2f} ({portfolio.get('pnl_percent',0):.1f}%)
📊 Open: {portfolio.get('open_positions',0)} | Closed: {portfolio.get('closed_positions',0)}
📉 Max DD: {portfolio.get('max_dd',0):.1%}
🎯 Win Rate: {portfolio.get('win_rate',0):.1%}

Today: ${portfolio.get('today_pnl',0):.2f} | Week: ${portfolio.get('week_pnl',0):.2f}
"""

    @staticmethod
    def format_positions(positions: List[Dict[str, Any]]) -> str:
        if not positions:
            return "📊 No open positions"
        msg = f"📈 **Open Positions ({len(positions)})**\n\n"
        for pos in positions[:10]:
            side = pos.get('side','LONG')
            emoji = "🟢" if side == "LONG" else "🔴"
            msg += f"{emoji} {pos.get('symbol')} {side} @ {pos.get('entry',0):.2f} → {pos.get('current',0):.2f} PnL: {pos.get('pnl',0):+.2f}% SL: {pos.get('sl',0):.2f} TP: {pos.get('tp',0):.2f}\n"
        return msg
