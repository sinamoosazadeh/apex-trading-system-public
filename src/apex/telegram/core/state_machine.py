
from __future__ import annotations
from enum import Enum
from typing import Dict, Set

class MenuState(str, Enum):
    MAIN = "main"
    BACKTEST = "backtest"
    BACKTEST_SYMBOL = "backtest_symbol"
    BACKTEST_TIMEFRAME = "backtest_timeframe"
    BACKTEST_CONFIRM = "backtest_confirm"
    BACKTEST_RUNNING = "backtest_running"
    BACKTEST_RESULT = "backtest_result"
    BACKTEST_CHARTS = "backtest_charts"
    
    TRADING = "trading"
    TRADING_PAPER = "trading_paper"
    TRADING_PAPER_SIGNALS = "trading_paper_signals"
    TRADING_LIVE = "trading_live"
    TRADING_LIVE_WARNING = "trading_live_warning"
    TRADING_LIVE_POSITIONS = "trading_live_positions"
    TRADING_LIVE_ORDERS = "trading_live_orders"
    TRADING_LIVE_BALANCE = "trading_live_balance"
    TRADING_LIVE_POSITION_DETAIL = "trading_live_position_detail"
    TRADING_LIVE_EMERGENCY = "trading_live_emergency"
    
    OPTIMIZATION = "optimization"
    OPTIMIZATION_RUN = "optimization_run"
    OPTIMIZATION_SYMBOL = "optimization_symbol"
    OPTIMIZATION_TIMEFRAME = "optimization_timeframe"
    OPTIMIZATION_TYPE = "optimization_type"
    OPTIMIZATION_TRIALS = "optimization_trials"
    OPTIMIZATION_VALIDATION = "optimization_validation"
    OPTIMIZATION_CONFIRM = "optimization_confirm"
    OPTIMIZATION_RUNNING = "optimization_running"
    OPTIMIZATION_JOBS = "optimization_jobs"
    OPTIMIZATION_VERSIONS = "optimization_versions"
    OPTIMIZATION_REPORTS = "optimization_reports"
    OPTIMIZATION_ARTIFACTS = "optimization_artifacts"
    OPTIMIZATION_ROLLBACK = "optimization_rollback"
    
    PORTFOLIO = "portfolio"
    PORTFOLIO_SUMMARY = "portfolio_summary"
    PORTFOLIO_POSITIONS = "portfolio_positions"
    PORTFOLIO_CLOSED = "portfolio_closed"
    PORTFOLIO_PERFORMANCE = "portfolio_performance"
    
    REPORTS = "reports"
    REPORTS_PERFORMANCE = "reports_performance"
    REPORTS_TRADES = "reports_trades"
    REPORTS_BACKTESTS = "reports_backtests"
    REPORTS_OPTIMIZER = "reports_optimizer"
    REPORTS_RISK = "reports_risk"
    REPORTS_EXPORT = "reports_export"
    
    MARKET = "market"
    MARKET_OVERVIEW = "market_overview"
    MARKET_SYMBOL = "market_symbol"
    
    SETTINGS = "settings"
    SETTINGS_GENERAL = "settings_general"
    SETTINGS_NOTIFICATIONS = "settings_notifications"
    SETTINGS_RISK = "settings_risk"
    SETTINGS_LANGUAGE = "settings_language"
    
    ADMIN = "admin"
    ADMIN_DASHBOARD = "admin_dashboard"
    ADMIN_HEALTH = "admin_health"
    ADMIN_LOGS = "admin_logs"
    ADMIN_USERS = "admin_users"
    ADMIN_FEATURES = "admin_features"
    ADMIN_EMERGENCY = "admin_emergency"
    
    HELP = "help"
    STATUS = "status"

# Valid transitions per blueprint - no dead ends
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    MenuState.MAIN: {MenuState.BACKTEST, MenuState.TRADING, MenuState.OPTIMIZATION, MenuState.REPORTS, MenuState.MARKET, MenuState.SETTINGS, MenuState.STATUS, MenuState.HELP, MenuState.ADMIN, MenuState.PORTFOLIO},
    MenuState.BACKTEST: {MenuState.BACKTEST_SYMBOL, MenuState.MAIN},
    MenuState.BACKTEST_SYMBOL: {MenuState.BACKTEST_TIMEFRAME, MenuState.BACKTEST, MenuState.MAIN},
    MenuState.BACKTEST_TIMEFRAME: {MenuState.BACKTEST_CONFIRM, MenuState.BACKTEST_SYMBOL, MenuState.MAIN},
    MenuState.BACKTEST_CONFIRM: {MenuState.BACKTEST_RUNNING, MenuState.BACKTEST_TIMEFRAME, MenuState.MAIN},
    MenuState.BACKTEST_RUNNING: {MenuState.BACKTEST_RESULT, MenuState.MAIN},
    MenuState.BACKTEST_RESULT: {MenuState.BACKTEST_CHARTS, MenuState.REPORTS, MenuState.OPTIMIZATION, MenuState.TRADING, MenuState.BACKTEST, MenuState.MAIN},
    MenuState.TRADING: {MenuState.TRADING_PAPER, MenuState.TRADING_LIVE, MenuState.MAIN},
    MenuState.TRADING_PAPER: {MenuState.TRADING_PAPER_SIGNALS, MenuState.PORTFOLIO, MenuState.MAIN},
    MenuState.TRADING_LIVE_WARNING: {MenuState.TRADING_LIVE, MenuState.TRADING, MenuState.MAIN},
    MenuState.TRADING_LIVE: {MenuState.TRADING_LIVE_POSITIONS, MenuState.TRADING_LIVE_ORDERS, MenuState.TRADING_LIVE_BALANCE, MenuState.TRADING_LIVE_EMERGENCY, MenuState.MAIN},
    MenuState.OPTIMIZATION: {MenuState.OPTIMIZATION_RUN, MenuState.OPTIMIZATION_JOBS, MenuState.OPTIMIZATION_VERSIONS, MenuState.OPTIMIZATION_REPORTS, MenuState.MAIN},
    MenuState.OPTIMIZATION_RUN: {MenuState.OPTIMIZATION_SYMBOL, MenuState.MAIN},
    MenuState.OPTIMIZATION_SYMBOL: {MenuState.OPTIMIZATION_TIMEFRAME, MenuState.OPTIMIZATION, MenuState.MAIN},
    MenuState.OPTIMIZATION_TIMEFRAME: {MenuState.OPTIMIZATION_TYPE, MenuState.OPTIMIZATION_SYMBOL, MenuState.MAIN},
    MenuState.OPTIMIZATION_TYPE: {MenuState.OPTIMIZATION_TRIALS, MenuState.OPTIMIZATION_TIMEFRAME, MenuState.MAIN},
    MenuState.OPTIMIZATION_TRIALS: {MenuState.OPTIMIZATION_CONFIRM, MenuState.OPTIMIZATION_TYPE, MenuState.MAIN},
    MenuState.PORTFOLIO: {MenuState.PORTFOLIO_SUMMARY, MenuState.PORTFOLIO_POSITIONS, MenuState.MAIN},
}

class StateMachine:
    def __init__(self):
        self.current_state: MenuState = MenuState.MAIN
    
    def can_transition(self, from_state: str, to_state: str) -> bool:
        # Allow always to main and back
        if to_state == MenuState.MAIN or to_state.endswith("_back"):
            return True
        # Check valid transitions
        allowed = VALID_TRANSITIONS.get(from_state, set())
        # Also allow any state to go to its parent and main
        return to_state in allowed or to_state in [s.value for s in MenuState]
    
    def transition(self, from_state: str, to_state: str) -> bool:
        if self.can_transition(from_state, to_state):
            self.current_state = MenuState(to_state) if to_state in [s.value for s in MenuState] else self.current_state
            return True
        return False
