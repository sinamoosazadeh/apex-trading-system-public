
from __future__ import annotations
from typing import Dict, Any, List

class BacktestFormatter:
    @staticmethod
    def format_signals(signals: List[Dict[str, Any]], limit: int = 25) -> str:
        if not signals:
            return "No signals found."
        msg = f"📈 **Last {min(limit, len(signals))} Signals**\n\n"
        for sig in signals[:limit]:
            side = sig.get('side', 'BUY')
            price = sig.get('price', 0)
            result = sig.get('result', 'Open')
            pnl = sig.get('pnl', 0)
            emoji = "🟢" if side == "BUY" else "🔴"
            msg += f"{emoji} {side} @ {price:.2f} - {result}"
            if pnl:
                msg += f" {pnl:+.2f}%"
            msg += "\n"
        return msg
    
    @staticmethod
    def format_metrics(metrics: Dict[str, Any]) -> str:
        return f"""📊 **Backtest Metrics**

• Net Profit: {metrics.get('net_profit',0):.2f}
• Gross Profit: {metrics.get('gross_profit',0):.2f}
• Gross Loss: {metrics.get('gross_loss',0):.2f}
• Profit Factor: {metrics.get('profit_factor',0):.2f}
• Win Rate: {metrics.get('win_rate',0):.1%}
• Sharpe: {metrics.get('sharpe',0):.2f}
• Sortino: {metrics.get('sortino',0):.2f}
• Calmar: {metrics.get('calmar',0):.2f}
• Max DD: {metrics.get('max_dd',0):.1%}
• Trades: {metrics.get('trades',0)}
• Expectancy: {metrics.get('expectancy',0):.4f}
• Avg RR: {metrics.get('avg_rr',0):.2f}
• Recovery: {metrics.get('recovery',0):.2f}
"""

    @staticmethod
    def format_ai_analysis(metrics: Dict[str, Any]) -> str:
        win_rate = metrics.get('win_rate',0)
        pf = metrics.get('profit_factor',0)
        sharpe = metrics.get('sharpe',0)
        dd = metrics.get('max_dd',0)
        
        analysis = "🧠 **AI Analysis**\n\n"
        
        if win_rate > 0.6 and pf > 1.8 and sharpe > 2:
            analysis += "✅ Excellent trend detection\n"
            analysis += "✅ High profit factor\n"
            analysis += "✅ Low drawdown\n\n"
            analysis += "💡 Recommendation: Live Trading ★★★★★\n"
            analysis += "Risk: 1.2% per trade, Leverage 3x\n"
        elif win_rate > 0.5 and pf > 1.3:
            analysis += "✅ Good performance in trends\n"
            analysis += "⚠️ Weak in ranging markets\n\n"
            analysis += "💡 Recommendation: Paper Trading ★★★★\n"
            analysis += "Run Optimization for improvement\n"
        else:
            analysis += "⚠️ Performance needs improvement\n"
            analysis += "❌ Low win rate or profit factor\n\n"
            analysis += "💡 Recommendation: Optimization Required\n"
            analysis += "Avoid Live Trading\n"
        
        if dd > 0.15:
            analysis += "\n⚠️ High Drawdown - Reduce risk\n"
        
        return analysis
