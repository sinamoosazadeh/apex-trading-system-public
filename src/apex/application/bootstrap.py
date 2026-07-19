
"""Application Bootstrap - Full Institutional - Crypto-Only 10 coins x 14 TFs + Backtest + Telegram Menu"""
from __future__ import annotations

import asyncio
import signal
import logging
import os
from collections import defaultdict
from typing import Dict, List

from ..core.events import EventBus, Event
from ..core.types.enums import EventType, OrderStatus
from ..domain.market import MarketBar
from ..domain.trading import Position
from ..domain.knowledge import Experience
from ..infrastructure.exchanges.toobit_ws import ToobitWebSocketClient
from ..infrastructure.exchanges.toobit_adapter import ToobitAdapter
from ..engines.probability_engine import ProbabilityEngine
from ..engines.governance import GovernanceEngine, GovernancePolicy
from ..engines.decision_engine import DecisionEngine
from ..engines.risk_engine import RiskEngine
from ..engines.portfolio_engine import PortfolioEngine
from ..engines.execution_engine import ExecutionEngine
from ..features.feature_store import FeatureStore
from ..features.primitives import PrimitiveFeatures
from ..features.structure import update_structure, StructureState, detect_fvgs, detect_order_blocks
from ..features.regime_engine import RegimeEngine
from ..features.ict_engine import ICTEngine
from ..features.order_flow_engine import order_flow_engine
from ..features.liquidity_engine import detect_liquidity_sweep, liquidity_score
from ..features.smt_engine import detect_smt_divergence, SMTState
from ..features.evidence_engine import EvidenceEngine
from ..monitoring.structured_logger import StructuredLogger
from ..monitoring.metrics_engine import MetricsEngine
from ..monitoring.health_monitor import HealthMonitor
from ..backtest.backtest_engine import InstitutionalBacktestEngine, TOP_10_SYMBOLS, ALL_14_TFS
from ..security.vault import Vault
from ..backtest.telegram_menu import handle_backtest_callback, BOT_MENU

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = StructuredLogger("APEX.Crypto")

class CryptoApplication:
    def __init__(self, api_key: str = None, api_secret: str = None, symbols: List[str] = None, initial_capital: float = 10000.0):
        self.symbols = symbols or TOP_10_SYMBOLS
        self.timeframes = ALL_14_TFS
        self.initial_capital = initial_capital
        self._running = False
        
        self.event_bus = EventBus()
        self.metrics = MetricsEngine()
        self.health = HealthMonitor()
        self.vault = Vault(master_password=os.getenv("APEX_MASTER", "default"))
        self.feature_store = FeatureStore()
        
        # Feature Engines
        self.primitive_features = PrimitiveFeatures(store=self.feature_store)
        self.regime_engine = RegimeEngine()
        self.ict_engine = ICTEngine()
        self.evidence_engine = EvidenceEngine()
        self.probability_engine = ProbabilityEngine()
        self.governance = GovernanceEngine(GovernancePolicy())
        self.decision_engine = DecisionEngine(self.governance)
        self.risk_engine = RiskEngine()
        self.portfolio_engine = PortfolioEngine(initial_capital=initial_capital)
        self.execution_engine = ExecutionEngine(api_key, api_secret)
        self.backtest_engine = InstitutionalBacktestEngine()
        
        # State
        self.bars_history: Dict[str, Dict[str, List[MarketBar]]] = defaultdict(lambda: defaultdict(list))
        self._structure_state: Dict[str, StructureState] = defaultdict(StructureState)
        self.last_processed_ts: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.smt_state = SMTState()
        
        # WebSocket - correct signature per toobit_ws.py: (event_bus, symbols)
        self.ws_client = ToobitWebSocketClient(event_bus=self.event_bus, symbols=self.symbols)
        
        # Telegram Bot (optional)
        self.telegram_bot = None
        
        log.info(f"Initializing Crypto-Only APEX - Toobit 10 coins, 14 TFs, 13 evidences...")
        log.info(f"Symbols: {self.symbols}")
        log.info(f"Timeframes: {self.timeframes}")
        log.info(f"Forex sessions REMOVED - 24/7 crypto mode per user request")

    async def initialize(self):
        self.event_bus.subscribe(EventType.NEW_CANDLE, self._on_new_candle)
        self.event_bus.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
        log.info("CryptoApplication initialized - Backtest ready")

    async def _on_new_candle(self, event: Event) -> None:
        bar_data = event.payload.get("bar")
        if not bar_data:
            return
        bar = MarketBar(**bar_data)
        tf = getattr(bar, 'timeframe', '1h')
        symbol = bar.symbol

        history_dict = self.bars_history[symbol]
        history = history_dict[tf]
        
        if self.last_processed_ts[symbol][tf] == bar.timestamp:
            if history and history[-1].timestamp == bar.timestamp:
                history[-1] = bar
            return
        self.last_processed_ts[symbol][tf] = bar.timestamp
        history.append(bar)
        if len(history) > 200:
            history.pop(0)
        if len(history) < 20:
            log.info(f"Collecting {symbol} {tf}: {len(history)}/20")
            return
        
        # 1. Primitive
        atr_feat = self.primitive_features.calculate_atr(history, 14, symbol, tf)
        rsi_feat = self.primitive_features.calculate_rsi(history, 14, symbol, tf)
        
        # 2. Regime
        regime = self.regime_engine.detect_regime(history)
        
        # 3. Structure
        highs = [b.high for b in history]
        lows = [b.low for b in history]
        closes = [b.close for b in history]
        opens = [b.open for b in history]
        volumes = [b.volume for b in history]
        struct_state = self._structure_state[symbol]
        self._structure_state[symbol] = update_structure(struct_state, highs, lows, closes, atr_feat.value)
        
        # 4. ICT Full (no forex)
        ict_state = self.ict_engine.analyze(highs, lows, closes, self._structure_state[symbol], atr_feat.value)
        
        # 5. Order Flow
        of_signal = order_flow_engine(highs, lows, closes, opens, volumes)
        
        # 6. Liquidity
        sweeps = detect_liquidity_sweep(highs, lows, closes, atr_feat.value)
        liq_score = liquidity_score(sweeps, of_signal.absorption_score)

        # 7. SMT (crypto pairs: BTC vs others)
        smt_signals = []
        if symbol != "BTC-SWAP-USDT" and "BTC-SWAP-USDT" in self.bars_history:
            btc_hist_dict = self.bars_history["BTC-SWAP-USDT"]
            if tf in btc_hist_dict and len(btc_hist_dict[tf]) >= 50:
                btc_h = [b.high for b in btc_hist_dict[tf]]
                btc_l = [b.low for b in btc_hist_dict[tf]]
                sigs, self.smt_state = detect_smt_divergence(symbol, highs, lows, "BTC-SWAP-USDT", btc_h, btc_l, self.smt_state)
                smt_signals = sigs

        # 8. 13 Evidences Engine
        evidence_bundle = self.evidence_engine.compute_all(
            highs=highs, lows=lows, closes=closes, opens=opens, volumes=volumes,
            atr=atr_feat.value, rsi=rsi_feat.value,
            structure_state=self._structure_state[symbol],
            ict_state=ict_state,
            of_signal=of_signal,
            sweeps=sweeps,
            smt_signals=smt_signals,
            regime=regime
        )

        # 9. Build evidence for Probability Engine (13 evidences)
        ev_long = {}
        ev_short = {}
        for ev_name, ev_result in evidence_bundle.items():
            ev_long[ev_name] = ev_result.long_score
            ev_short[ev_name] = ev_result.short_score

        weights = self.evidence_engine.get_default_weights()

        prob_report = self.probability_engine.compute_probability(ev_long, ev_short, weights)

        # 10. Decision - using evaluate per fixed API
        contributors_long = len([v for v in ev_long.values() if v > 0.6])
        contributors_short = len([v for v in ev_short.values() if v > 0.6])
        decision = self.decision_engine.evaluate(prob_report, self.portfolio_engine.get_state(), contributors_long, contributors_short)

        # 11. Risk & Execution
        if decision.decision_type == "TRADE":
            blueprint = self.risk_engine.create_blueprint(
                symbol=symbol,
                direction=decision.direction,
                entry_price=closes[-1],
                atr=atr_feat.value,
                structure_state=self._structure_state[symbol]
            )
            await self.execution_engine.execute_blueprint(blueprint)

    async def _on_order_filled(self, event: Event):
        pass

    async def run_backtest(self, symbol: str, timeframe: str, bars: List[MarketBar]):
        """Public API for Telegram bot - Full history backtest"""
        result = self.backtest_engine.run_backtest_on_bars(bars, symbol, timeframe)
        report = self.backtest_engine.generate_comprehensive_report(result)
        return result, report

    async def run(self):
        await self.initialize()
        self._running = True
        log.info(f"Starting Crypto APEX - {len(self.symbols)} symbols, {len(self.timeframes)} TFs")
        if self.ws_client:
            await self.ws_client.start()
        # Keep running
        while self._running:
            await asyncio.sleep(1)

    def stop(self):
        self._running = False

# For backward compatibility with tests
Application = CryptoApplication

try:
    from ..optimization.integration import integrate_optimization_system
    integrate_optimization_system(self)
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"Optimization integration skipped: {e}")

