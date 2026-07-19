
from ..utils.keyboard_builder import KeyboardBuilder

class ReportsMenu:
    @staticmethod
    def main_menu():
        return {
            "message": """📁 **Reports Center**

Available reports:
• Performance - Net, PF, Sharpe, etc
• Portfolio - Balance, PnL
• Trades - All trades history
• Optimizer - Optimization results
• Backtests - All backtests
• Risk - Drawdown, exposure
• Exchange - Fees, funding
• Audit - All actions log

All reports exportable: PDF, CSV, Excel, JSON
""",
            "keyboard": KeyboardBuilder.build([
                [{"text": "📊 Performance", "callback": "reports.performance"}, {"text": "💼 Portfolio", "callback": "reports.portfolio"}],
                [{"text": "📋 Trades", "callback": "reports.trades"}, {"text": "🧠 Optimizer", "callback": "reports.optimizer"}],
                [{"text": "📈 Backtests", "callback": "reports.backtests"}, {"text": "⚠️ Risk", "callback": "reports.risk"}],
                [{"text": "📤 Export Center", "callback": "reports.export.menu"}],
                [{"text": "📋 Audit Log", "callback": "reports.audit"}],
            ], current_menu="reports")
        }
