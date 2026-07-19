"""Backtesting Engine - Full history, clean state, advanced metrics."""
from __future__ import annotations
import asyncio
import logging
import math
from typing import List
from ..domain.market import MarketBar
from ..engines.kernel import CentralDecisionKernel
from ..infrastructure.exchanges.toobit_adapter import ToobitAdapter

log = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(self, kernel: CentralDecisionKernel, adapter: ToobitAdapter):
        self.kernel = kernel
        self.adapter = adapter

    async def run_backtest(self, symbol: str, timeframe: str, limit: int = 0) -> dict:
        log.info(f"Starting FULL HISTORY backtest for {symbol} on {timeframe}...")
        
        # 1. Reset system state for clean backtest
        from ..engines.portfolio_engine import PortfolioEngine
        self.kernel.portfolio_engine = PortfolioEngine(initial_capital=self.kernel.portfolio_engine.initial_capital)
        self.kernel.bars_history.clear()
        self.kernel.last_processed_ts.clear()
        self.kernel._structure_state = type(self.kernel._structure_state)()
        
        # 2. Fetch ALL available candles
        raw_klines = await self.adapter.client.get_all_klines(symbol, timeframe)
        total_bars = len(raw_klines)
        log.info(f"Fetched {total_bars} total candles for {symbol} {timeframe}")
        
        bars = [MarketBar(
            timestamp=k[0], open=float(k[1]), high=float(k[2]),
            low=float(k[3]), close=float(k[4]), volume=float(k[5]),
            symbol=symbol, exchange="toobit", timeframe=timeframe
        ) for k in raw_klines]
        
        original_mode = self.kernel.app.mode
        self.kernel.app.mode = "BACKTEST"
        
        # 3. Local signal collection to avoid race conditions
        collected_signals = []
        async def mock_send_signal(msg):
            collected_signals.append(msg)
            
        original_send_signal = self.kernel.app.send_telegram_signal
        self.kernel.app.send_telegram_signal = mock_send_signal
        
        for bar in bars:
            await self.kernel.process_bar(bar, ref_bar=None)
            
            for pos in list(self.kernel.portfolio_engine.open_positions.values()):
                if pos.symbol == symbol and pos.status == "OPEN":
                    hit_sl = (pos.direction == "LONG" and bar.low <= pos.stop_loss) or \
                             (pos.direction == "SHORT" and bar.high >= pos.stop_loss)
                    hit_tp = (pos.direction == "LONG" and bar.high >= pos.take_profit) or \
                             (pos.direction == "SHORT" and bar.low <= pos.take_profit)
                    if hit_sl or hit_tp:
                        exit_price = pos.stop_loss if hit_sl else pos.take_profit
                        await self.kernel.close_position_workflow(pos, exit_price, "Backtest SL/TP Hit")
        
        self.kernel.app.mode = original_mode
        self.kernel.app.send_telegram_signal = original_send_signal
        
        portfolio = self.kernel.portfolio_engine
        trades = portfolio.closed_trades
        
        # 4. Calculate Advanced Metrics
        metrics = self._calculate_metrics(trades, portfolio.initial_capital)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "total_bars": total_bars,
            "signals_for_display": collected_signals[-25:],
            "total_signals_generated": len(collected_signals),
            "metrics": metrics
        }

    def _calculate_metrics(self, trades: list, initial_capital: float) -> dict:
        if not trades:
            return {
                "total_trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
                "net_profit_pct": 0.0, "net_pnl": 0.0, "profit_factor": 0.0,
                "max_drawdown": 0.0, "max_consec_wins": 0, "max_consec_losses": 0,
                "sharpe": 0.0, "long_trades": 0, "short_trades": 0,
                "long_wins": 0, "short_wins": 0
            }
        
        total_trades = len(trades)
        wins = [t for t in trades if t.win]
        losses = [t for t in trades if not t.win]
        
        long_trades = [t for t in trades if t.direction == "LONG"]
        short_trades = [t for t in trades if t.direction == "SHORT"]
        
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        net_pnl = gross_profit - gross_loss
        net_profit_pct = (net_pnl / initial_capital) * 100
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        win_rate = (len(wins) / total_trades) * 100
        
        equity = initial_capital
        peak = equity
        max_dd = 0.0
        for t in trades:
            equity += t.pnl
            if equity > peak: peak = equity
            dd = (peak - equity) / peak * 100 if peak > 0 else 0
            if dd > max_dd: max_dd = dd
            
        streak_w = 0; max_streak_w = 0
        streak_l = 0; max_streak_l = 0
        for t in trades:
            if t.win:
                streak_w += 1; streak_l = 0
                if streak_w > max_streak_w: max_streak_w = streak_w
            else:
                streak_l += 1; streak_w = 0
                if streak_l > max_streak_l: max_streak_l = streak_l
                
        returns = [t.pnl / initial_capital for t in trades]
        mean_ret = sum(returns) / len(returns)
        std_dev = math.sqrt(sum((r - mean_ret)**2 for r in returns) / len(returns)) if len(returns) > 1 else 0
        sharpe = (mean_ret / std_dev) * math.sqrt(252) if std_dev > 0 else 0
        
        return {
            "total_trades": total_trades,
            "wins": len(wins), "losses": len(losses), "win_rate": win_rate,
            "net_profit_pct": net_profit_pct, "net_pnl": net_pnl,
            "profit_factor": profit_factor, "max_drawdown": max_dd,
            "max_consec_wins": max_streak_w, "max_consec_losses": max_streak_l,
            "sharpe": sharpe,
            "long_trades": len(long_trades), "short_trades": len(short_trades),
            "long_wins": len([t for t in long_trades if t.win]),
            "short_wins": len([t for t in short_trades if t.win])
        }
