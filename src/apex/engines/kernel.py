"""Central Decision Kernel - Multi-TF In-time support."""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from collections import defaultdict
from typing import Any

from ..core.events import EventBus, Event
from ..core.types.enums import EventType, OrderStatus
from ..domain.market import MarketBar, Tick, OrderBook
from ..domain.trading import Position, TradeBlueprint
from ..domain.knowledge import Experience
from ..domain.meta import MetaDecisionScore
from ..features.feature_store import FeatureStore
from ..features.primitives import PrimitiveFeatures
from ..features.regime_engine import RegimeEngine
from ..features.structure import update_structure, StructureState, detect_fvgs, detect_order_blocks
from ..engines.probability_engine import ProbabilityEngine
from ..engines.decision_engine import DecisionEngine
from ..engines.risk_engine import RiskEngine
from ..engines.portfolio_engine import PortfolioEngine
from ..engines.execution_engine import ExecutionEngine
from ..engines.digital_twin import DigitalTwin
from ..engines.meta_intelligence import MetaIntelligenceEngine
from ..research.research_engine import ResearchEngine
from ..monitoring.structured_logger import StructuredLogger
from ..monitoring.health_monitor import HealthMonitor

log = StructuredLogger("APEX.CDK")

class CentralDecisionKernel:
    def __init__(self, feature_store, prob_engine, decision_engine, risk_engine, portfolio_engine, execution_engine, research_engine, digital_twin, meta_engine, health_monitor, ref_symbol="ETH-USDT") -> None:
        self.app = None
        self.feature_store = feature_store
        self.prob_engine = prob_engine
        self.decision_engine = decision_engine
        self.risk_engine = risk_engine
        self.portfolio_engine = portfolio_engine
        self.execution_engine = execution_engine
        self.research_engine = research_engine
        self.digital_twin = digital_twin
        self.meta_engine = meta_engine
        self.health = health_monitor
        
        self.primitive_features = PrimitiveFeatures(feature_store)
        self.regime_engine = RegimeEngine()
        self._structure_state = StructureState()
        self.bars_history: dict[str, list[MarketBar]] = defaultdict(list)
        self.last_processed_ts: dict[str, float] = defaultdict(float)

    async def process_bar(self, bar: MarketBar, ref_bar: MarketBar | None = None) -> None:
        self.health.heartbeat("CDK")
        key = f"{bar.symbol}_{bar.timeframe}"
        history = self.bars_history[key]
        
        # INJECT OPTIMIZED PARAMETERS IF AVAILABLE
        if self.app and hasattr(self.app, 'optimizer'):
            opt_params = self.app.optimizer.optimized_params.get((bar.symbol, bar.timeframe))
            if opt_params:
                self.decision_engine.governance.policy = opt_params["policy"]
                self.risk_engine.risk_per_trade_pct = opt_params["risk_pct"]
                self.risk_engine.sl_mult = opt_params["sl_mult"]
                self.risk_engine.tp_mult = opt_params["tp_mult"]
        
        if self.last_processed_ts[key] == bar.timestamp:
            if history and history[-1].timestamp == bar.timestamp:
                history[-1] = bar
            return
            
        self.last_processed_ts[key] = bar.timestamp
        history.append(bar)
        if len(history) > 50: history.pop(0)
        
        if len(history) < 20:
            log.info(f"Collecting data for {key}: {len(history)}/20 bars.")
            return

        try:
            atr_feat = self.primitive_features.calculate_atr(history, 14, bar.symbol, bar.timeframe)
            rsi_feat = self.primitive_features.calculate_rsi(history, 14, bar.symbol, bar.timeframe)
            regime = self.regime_engine.detect_regime(history)
            
            highs = [b.high for b in history]
            lows = [b.low for b in history]
            closes = [b.close for b in history]
            self._structure_state = update_structure(self._structure_state, highs, lows, closes, atr_feat.value)
            
            obs = detect_order_blocks(history, self._structure_state.bos_up, self._structure_state.bos_dn)
            bull_fvg, bear_fvg = detect_fvgs(history)
            
            mom_long = max(0.0, min(1.0, (45.0 - rsi_feat.value) / 25.0)) if rsi_feat.value < 45 else 0.0
            mom_short = max(0.0, min(1.0, (rsi_feat.value - 55.0) / 25.0)) if rsi_feat.value > 55 else 0.0
            
            ev_long = {
                "momentum": mom_long,
                "structure": 1.0 if self._structure_state.bos_up or self._structure_state.choch_up else 0.2,
                "fvg": 0.9 if bull_fvg else 0.1,
                "ob": 0.9 if any(ob.top > bar.close for ob in obs) else 0.1,
                "order_flow": 0.8,
                "smt": 0.0
            }
            ev_short = {
                "momentum": mom_short,
                "structure": 1.0 if self._structure_state.bos_dn or self._structure_state.choch_dn else 0.2,
                "fvg": 0.9 if bear_fvg else 0.1,
                "ob": 0.9 if any(ob.bot < bar.close for ob in obs) else 0.1,
                "order_flow": 0.8,
                "smt": 0.0
            }
            weights = {"momentum": 0.25, "structure": 0.30, "fvg": 0.15, "ob": 0.15, "order_flow": 0.10, "smt": 0.05}
            
            prob_report = self.prob_engine.compute_probability(ev_long, ev_short, weights, trend_confidence=regime.trend_confidence)
            portfolio_state = self.portfolio_engine.get_state()
            
            contributors_long = len([v for v in ev_long.values() if v > 0.35])
            contributors_short = len([v for v in ev_short.values() if v > 0.35])
            
            decision = self.decision_engine.evaluate(prob_report, portfolio_state, contributors_long=contributors_long, contributors_short=contributors_short)
            
            if decision.decision_type == "TRADE":
                await self._execute_trade_workflow(decision, prob_report, portfolio_state, bar, atr_feat.value, history)
                
        except Exception as e:
            log.error("CDK Pipeline failed", error=str(e), symbol=bar.symbol)

    async def _execute_trade_workflow(self, decision, prob_report, portfolio_state, bar, atr, history) -> None:
        blueprint = self.risk_engine.create_blueprint(
            decision, portfolio_state, prob_report, bar.close, atr,
            structure_low=min(b.low for b in history[-5:]) if history else None,
            structure_high=max(b.high for b in history[-5:]) if history else None
        )
        if not blueprint: return
            
        is_safe, _ = self.digital_twin.simulate_blueprint(blueprint)
        if not is_safe: return
            
        emoji = "🟢" if decision.direction == "LONG" else "🔴"
        msg = (f"{emoji} *New Signal*\nSymbol: `{bar.symbol}`\nTF: `{bar.timeframe}`\nDir: *{decision.direction}*\n"
               f"Entry: `{bar.close:.2f}`\nSL: `{blueprint.stop_loss:.2f}`\nTP: `{blueprint.take_profit:.2f}`")
        
        if self.app:
            await self.app.send_telegram_signal(msg)
            
        if self.app and self.app.mode in ["LIVE", "BACKTEST"]:
            order_id = str(uuid.uuid4())
            if self.app.mode == "LIVE":
                order_response = await self.execution_engine.execute_blueprint(blueprint)
                status = order_response.get("status")
                if isinstance(status, OrderStatus): status = status.value
                if status not in ["NEW", "PARTIALLY_FILLED", "FILLED"]: return
                order_id = order_response.get("orderId", order_id)
            
            position = Position(
                position_id=order_id, blueprint_id=blueprint.decision_id, symbol=bar.symbol, exchange="toobit",
                direction=decision.direction, entry_price=bar.close, quantity=blueprint.position_size,
                stop_loss=blueprint.stop_loss, take_profit=blueprint.take_profit
            )
            self.portfolio_engine.add_position(position)
            exp = Experience(
                trade_id=position.position_id, symbol=bar.symbol, setup_name="Institutional_CDK",
                direction=decision.direction, win=False, r_multiple=0.0, 
                probability_at_entry=prob_report.probability_long if decision.direction == "LONG" else prob_report.probability_short,
                uncertainty_at_entry=prob_report.uncertainty, regime="neutral"
            )
            self.research_engine.record_trade_context(position.position_id, exp)

    async def close_position_workflow(self, position: Position, exit_price: float, reason: str) -> None:
        trade = self.portfolio_engine.close_position(position.position_id, exit_price)
        if trade:
            self.research_engine.process_closed_trade(trade)
            self.meta_engine.record_decision_outcome(MetaDecisionScore(
                decision_id=trade.position_id, expected_probability=0.8, actual_outcome=trade.win,
                calibration_error=abs(0.8 - (1.0 if trade.win else 0.0)), attribution_accuracy=1.0
            ))
            emoji = "✅" if trade.pnl > 0 else "❌"
            status_text = "Win" if trade.pnl > 0 else "Loss"
            msg = (f"{emoji} *Trade Closed ({status_text})*\nSymbol: `{trade.symbol}`\nPnL: `{trade.pnl:.2f} USDT`\nR: `{trade.r_multiple:.2f}`")
            if self.app: await self.app.send_telegram_signal(msg)

    def process_tick(self, tick: Tick) -> None: pass
    def process_orderbook(self, book: OrderBook) -> None: pass
