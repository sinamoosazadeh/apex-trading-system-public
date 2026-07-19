
from typing import Dict, Any, List

class PortfolioController:
    def __init__(self, portfolio_engine=None, app=None):
        self.portfolio_engine = portfolio_engine
        self.app = app
    
    def get_summary(self) -> Dict[str, Any]:
        if self.portfolio_engine:
            try:
                return {
                    "balance": getattr(self.portfolio_engine, 'balance', 10000),
                    "equity": getattr(self.portfolio_engine, 'equity', 10150),
                    "pnl": getattr(self.portfolio_engine, 'total_pnl', 150),
                    "open_positions": len(getattr(self.portfolio_engine, 'positions', [])),
                    "max_dd": 0.08,
                    "win_rate": 0.62,
                    "today_pnl": 45,
                    "week_pnl": 210,
                }
            except:
                pass
        return {
            "balance": 10000, "equity": 10150, "pnl": 150, "pnl_percent": 1.5,
            "open_positions": 1, "closed_positions": 45,
            "max_dd": 0.08, "win_rate": 0.62, "today_pnl": 45, "week_pnl": 210
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        if self.portfolio_engine and hasattr(self.portfolio_engine, 'positions'):
            return self.portfolio_engine.positions
        return []
    
    def get_closed_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.portfolio_engine and hasattr(self.portfolio_engine, 'closed_trades'):
            return self.portfolio_engine.closed_trades[-limit:]
        return []
