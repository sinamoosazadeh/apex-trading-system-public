
"""Application Bootstrap - Crypto-Only Institutional Version.
Per User Request 2026-07-19:
- Only crypto market, Toobit only
- 10 top cap coins
- 14 timeframes, all candles available
- No forex sessions (Asia/London/NY REMOVED)
- Uses 13 evidences + SMT + OrderFlow + Liquidity + ICT
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List

from ..core.events import EventBus, Event
from ..core.types.enums import EventType
from ..core.config import ApexConfigLoader
from ..security.vault import SecureBootstrapLoader
from ..domain.market import MarketBar
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
from ..features.smt_engine import detect_smt_divergence, SMTState
from ..features.order_flow_engine import order_flow_engine
from ..features.liquidity_engine import detect_liquidity_sweep, liquidity_score
from ..features.ict_engine import ICTEngine
from ..features.evidence_engine import EvidenceEngine
from ..features.session_filter import SESSION_FILTER
from ..research.knowledge_base import KnowledgeBase
from ..research.research_engine import ResearchEngine
from ..monitoring.structured_logger import StructuredLogger
from ..monitoring.metrics_engine import MetricsEngine
from ..monitoring.health_monitor import HealthMonitor

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = StructuredLogger("APEX.Crypto")

# Toobit 10 top cap + 14 timeframes per user spec
TOOBIT_TOP_10 = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT"
]

TOOBIT_14_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1M"
]

class CryptoApplication:
    def __init__(self, api_key: str, api_secret: str, symbols: List[str] | None = None, initial_capital: float = 10000.0) -> None:
        self.symbols = symbols or TOOBIT_TOP_10
        self.timeframes = TOOBIT_14_TIMEFRAMES
        self._running = False
        
        self.event_bus = EventBus()
        self.metrics = MetricsEngine()
        self.health = HealthMonitor()
        
        self.feature_store = FeatureStore()
        self.primitive_features = PrimitiveFeatures(self.feature_store)
        self.regime_engine = RegimeEngine()
        self.ict_engine = ICTEngine()
        self.evidence_engine = EvidenceEngine()
        self.smt_state = SMTState()
        
        self.bars_history: Dict[str, Dict[str, List[MarketBar]]] = defaultdict(lambda: defaultdict(list))
        self.last_processed_ts: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._structure_state: Dict[str, StructureState] = defaultdict(StructureState)
        
        self.probability_engine = ProbabilityEngine()
        self.knowledge_base = KnowledgeBase()
        self.research_engine = ResearchEngine(self.knowledge_base, self.probability_engine)
        self.portfolio_engine = PortfolioEngine(initial_capital=initial_capital)
        self.governance = GovernanceEngine(GovernancePolicy())
        self.decision_engine = DecisionEngine(self.governance)
        self.risk_engine = RiskEngine()
        
        self.toobit_adapter = ToobitAdapter(api_key, api_secret)
        self.execution_engine = ExecutionEngine(self.toobit_adapter)
        self.ws_client = ToobitWebSocketClient(self.event_bus, self.symbols)
        
        for mod in ["Application", "ProbabilityEngine", "ExecutionEngine", "WebSocket", "EvidenceEngine", "SMT", "OrderFlow"]:
            self.health.register_module(mod)

    async def initialize(self) -> None:
        log.info("Initializing Crypto-Only APEX - Toobit 10 coins, 14 TFs, 13 evidences...")
        log.info(f"Symbols: {self.symbols}")
        log.info(f"Timeframes: {self.timeframes}")
        log.info("Forex sessions REMOVED - 24/7 crypto mode per user request")
        self.event_bus.subscribe(EventType.NEW_CANDLE, self._on_new_candle)
        self.event_bus.subscribe(EventType.NEW_TICK, self._on_new_tick)

    async def _on_new_tick(self, event: Event) -> None:
        self.health.heartbeat("WebSocket")
        tick_data = event.payload.get("tick")
        if not tick_data:
            return
        symbol = tick_data["symbol"]
        # Crypto 24/7 - no session filter
        session = SESSION_FILTER.is_trading_allowed(symbol)
        if not session.is_active:
            return
        current_price = tick_data["price"]
        self.portfolio_engine.update_positions({symbol: current_price})
        for pos in list(self.portfolio_engine.open_positions.values()):
            if pos.symbol != symbol or pos.status != "OPEN":
                continue
            hit_sl = (pos.direction == "LONG" and current_price <= pos.stop_loss) or (pos.direction == "SHORT" and current_price >= pos.stop_loss)
            hit_tp = (pos.direction == "LONG" and current_price >= pos.take_profit) or (pos.direction == "SHORT" and current_price <= pos.take_profit)
            if hit_sl or hit_tp:
                await self._close_position(pos, current_price, "SL/TP Hit")

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
        if symbol != "BTCUSDT" and "BTCUSDT" in self.bars_history:
            btc_hist_dict = self.bars_history["BTCUSDT"]
            if tf in btc_hist_dict and len(btc_hist_dict[tf]) >= 50:
                btc_h = [b.high for b in btc_hist_dict[tf]]
                btc_l = [b.low for b in btc_hist_dict[tf]]
                sigs, self.smt_state = detect_smt_divergence(symbol, highs, lows, "BTCUSDT", btc_h, btc_l, self.smt_state)
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
            # ev_result has long_score, short_score
            ev_long[ev_name] = ev_result.long_score
            ev_short[ev_name] = ev_result.short_score
        
        weights = self.evidence_engine.get_default_weights()
        
        prob_report = self.probability_engine.compute_probability(ev_long, ev_short, weights)
        
        # 10. Decision
        decision = self.decision_engine.make_decision(prob_report, regime, symbol)
        if not decision or decision.decision_type != "TRADE":
            return
        
        # 11. Risk
        blueprint = self.risk_engine.create_blueprint(
            decision=decision,
            portfolio=self.portfolio_engine.get_state(),
            probability_report=prob_report,
            current_price=closes[-1],
            atr=atr_feat.value,
            ob_bot=ict_state.ob_level if hasattr(ict_state, 'ob_level') else None,
            htf_high=max(highs[-50:]) if len(highs)>=50 else None
        )
        if not blueprint:
            return
        
        # 12. Execute
        result = await self.execution_engine.execute_blueprint(blueprint)
        log.info(f"Executed {symbol} {decision.direction} prob={prob_report.probability_long:.2f} {result}")

    async def _close_position(self, pos, price, reason):
        log.info(f"Closing {pos.symbol} {pos.direction} @ {price} reason={reason}")
        self.portfolio_engine.close_position(pos.position_id, price)

# Alias for backward compat
Application = CryptoApplication
