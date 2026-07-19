"""Background Meta-Optimizer - 14 TFs for BTC, 4 for Alts."""
from __future__ import annotations
import asyncio
import logging
import random
import copy
from typing import Any

log = logging.getLogger(__name__)

class MetaOptimizer:
    def __init__(self, app: Any):
        self.app = app
        self.kernel = app.kernel
        self.adapter = app.toobit_adapter
        self.running = False
        
        self.symbols = [
            "BTC-SWAP-USDT", "ETH-SWAP-USDT", "SOL-SWAP-USDT", "BNB-SWAP-USDT", 
            "XRP-SWAP-USDT", "DOGE-SWAP-USDT", "ADA-SWAP-USDT", "AVAX-SWAP-USDT", 
            "LINK-SWAP-USDT", "DOT-SWAP-USDT"
        ]
        
        # BTC gets 14 TFs, Alts get 4 TFs
        self.btc_tfs = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "1w", "1M"]
        self.alt_tfs = ["5m", "15m", "1h", "4h"]
        
        self.queue = []
        for sym in self.symbols:
            tfs = self.btc_tfs if sym == "BTC-SWAP-USDT" else self.alt_tfs
            for tf in tfs:
                self.queue.append((sym, tf))
                
        self.queue_index = 0
        self.interval_seconds = 21600  # 6 hours (4x per day)
        self.optimized_params = {}

    async def run(self) -> None:
        self.running = True
        log.info("Meta-Optimizer started. 14 TFs for BTC, 4 for Alts. 4x/day.")
        await asyncio.sleep(120)
        
        while self.running and self.app._running:
            try:
                if self.queue_index >= len(self.queue):
                    self.queue_index = 0
                    log.info("Optimizer queue completed. Restarting cycle.")
                
                symbol, timeframe = self.queue[self.queue_index]
                await self._optimization_session(symbol, timeframe)
                self.queue_index += 1
                
            except Exception as e:
                log.error(f"Meta-Optimizer error: {e}")
            
            await asyncio.sleep(self.interval_seconds)

    async def _optimization_session(self, symbol: str, timeframe: str) -> None:
        log.info(f"Optimization session: {symbol} {timeframe}")
        from ..research.backtest_engine import BacktestEngine
        bt_engine = BacktestEngine(self.kernel, self.adapter)
        
        self.kernel.app.mode = "BACKTEST"
        baseline_result = await bt_engine.run_backtest(symbol, timeframe)
        baseline_pnl = baseline_result["metrics"]["net_pnl"]
        
        best_params = None
        best_risk = None
        best_pnl = baseline_pnl
        improved = False
        
        for i in range(3):
            cand_policy = self._mutate_policy(self.kernel.governance.policy)
            cand_risk = self._mutate_risk(self.kernel.risk_engine)
            
            self.kernel.governance.policy = cand_policy
            self.kernel.risk_engine.risk_per_trade_pct = cand_risk.risk_per_trade_pct
            self.kernel.risk_engine.sl_mult = cand_risk.sl_mult
            self.kernel.risk_engine.tp_mult = cand_risk.tp_mult
            
            result = await bt_engine.run_backtest(symbol, timeframe)
            pnl = result["metrics"]["net_pnl"]
            trades = result["metrics"]["total_trades"]
            
            if pnl > best_pnl and trades >= 2:
                best_pnl = pnl
                best_params = copy.deepcopy(cand_policy)
                best_risk = copy.deepcopy(cand_risk)
                improved = True
                log.info(f"  Iter {i+1}: Improvement! PnL={pnl:.2f}")
            else:
                self.kernel.governance.policy = self._get_baseline_policy()
                self.kernel.risk_engine.risk_per_trade_pct = 1.0
                self.kernel.risk_engine.sl_mult = 2.0
                self.kernel.risk_engine.tp_mult = 3.5
        
        self.kernel.app.mode = "PAPER"
        
        if improved and best_params:
            self.optimized_params[(symbol, timeframe)] = {
                "policy": best_params,
                "risk_pct": best_risk.risk_per_trade_pct,
                "sl_mult": best_risk.sl_mult,
                "tp_mult": best_risk.tp_mult
            }
            log.info(f"🚀 OPTIMIZED & STORED for {symbol} {timeframe}! PnL: {best_pnl:.2f}")
            
            if self.app.tg_bot:
                msg = (f"🔧 *Optimization Complete*\n"
                       f"Symbol: `{symbol}` | TF: `{timeframe}`\n"
                       f"New PnL: `{best_pnl:.2f} USDT`\n"
                       f"Params saved and injected.")
                await self.app.tg_bot.send_signal(msg)
        else:
            self.kernel.governance.policy = self._get_baseline_policy()
            self.kernel.risk_engine.risk_per_trade_pct = 1.0
            self.kernel.risk_engine.sl_mult = 2.0
            self.kernel.risk_engine.tp_mult = 3.5

    def _get_baseline_policy(self):
        from ..engines.governance import GovernancePolicy
        return GovernancePolicy()

    def _mutate_policy(self, baseline: Any) -> Any:
        mutated = copy.deepcopy(baseline)
        mutated.min_probability_threshold = self._clamp(baseline.min_probability_threshold + random.uniform(-0.03, 0.03), 0.25, 0.45)
        return mutated

    def _mutate_risk(self, baseline: Any) -> Any:
        from ..engines.risk_engine import RiskEngine
        mutated = RiskEngine()
        mutated.risk_per_trade_pct = self._clamp(baseline.risk_per_trade_pct + random.uniform(-0.2, 0.2), 0.5, 2.0)
        mutated.sl_mult = self._clamp(baseline.sl_mult + random.uniform(-0.2, 0.2), 1.5, 3.0)
        mutated.tp_mult = self._clamp(baseline.tp_mult + random.uniform(-0.3, 0.3), 2.5, 5.0)
        return mutated

    def _clamp(self, v: float, mn: float, mx: float) -> float:
        return max(mn, min(mx, round(v, 4)))

    async def stop(self) -> None:
        self.running = False
