"""Risk, Money Management & Execution Optimizer."""
from __future__ import annotations

import math
from typing import Any
import uuid

from ..domain.contracts import ProbabilityReport
from ..domain.trading import PortfolioState, TradeBlueprint, Decision

class RiskEngine:
    """Calculates optimal trade parameters and position sizing."""

    def __init__(self, risk_per_trade_pct: float = 1.0, sl_mult: float = 2.0, tp_mult: float = 3.5) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        self.fee_slippage_r: float = 0.02

    def _clamp(self, x: float, lo: float, hi: float) -> float:
        if math.isnan(x):
            return (lo + hi) / 2.0
        return max(lo, min(hi, x))

    def compute_stop_loss(
        self,
        entry_price: float,
        atr: float,
        direction: str,
        structure_low: float | None = None,
        structure_high: float | None = None,
        ob_bot: float | None = None,
        ob_top: float | None = None,
    ) -> float:
        """Compute stop loss using Structure Hybrid model."""
        if direction == "LONG":
            atr_sl = entry_price - (atr * self.sl_mult)
            
            struct_sl = None
            if ob_bot is not None and ob_bot > 0:
                struct_sl = ob_bot - (atr * 0.15)
            elif structure_low is not None and structure_low > 0:
                struct_sl = structure_low - (atr * 0.15)
                
            if struct_sl is not None and struct_sl > 0:
                risk_struct = entry_price - struct_sl
                max_risk = atr * self.sl_mult * 1.60
                min_risk = atr * 0.35
                if min_risk < risk_struct <= max_risk:
                    return struct_sl
                    
            return atr_sl
            
        else:  # SHORT
            atr_sl = entry_price + (atr * self.sl_mult)
            
            struct_sl = None
            if ob_top is not None and ob_top > 0:
                struct_sl = ob_top + (atr * 0.15)
            elif structure_high is not None and structure_high > 0:
                struct_sl = structure_high + (atr * 0.15)
                
            if struct_sl is not None and struct_sl > 0:
                risk_struct = struct_sl - entry_price
                max_risk = atr * self.sl_mult * 1.60
                min_risk = atr * 0.35
                if min_risk < risk_struct <= max_risk:
                    return struct_sl
                    
            return atr_sl

    def compute_take_profit(
        self,
        entry_price: float,
        stop_price: float,
        direction: str,
        htf_high: float | None = None,
        htf_low: float | None = None,
    ) -> tuple[float, float, float, float]:
        """Compute TP1, TP2, TP3 and final TP using liquidity targets."""
        risk_pts = abs(entry_price - stop_price)
        if risk_pts <= 0:
            return entry_price, entry_price, entry_price, entry_price

        base_rr = self.tp_mult / self.sl_mult

        if direction == "LONG":
            tp1 = entry_price + (risk_pts * base_rr * 0.50)
            tp2 = entry_price + (risk_pts * base_rr)
            tp3_candidate = entry_price + (risk_pts * base_rr * 1.50)
            
            if htf_high is not None and htf_high > tp2 and htf_high < tp3_candidate:
                tp3 = htf_high
            else:
                tp3 = tp3_candidate
        else:  # SHORT
            tp1 = entry_price - (risk_pts * base_rr * 0.50)
            tp2 = entry_price - (risk_pts * base_rr)
            tp3_candidate = entry_price - (risk_pts * base_rr * 1.50)
            
            if htf_low is not None and htf_low < tp2 and htf_low > tp3_candidate:
                tp3 = htf_low
            else:
                tp3 = tp3_candidate

        return tp1, tp2, tp3, tp3

    def compute_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_price: float,
        leverage: float = 1.0
    ) -> tuple[float, float]:
        """Calculate position size based on risk percentage."""
        risk_amount = capital * (self.risk_per_trade_pct / 100.0)
        risk_per_unit = abs(entry_price - stop_price)
        
        if risk_per_unit <= 0 or entry_price <= 0:
            return 0.0, 0.0
            
        position_size = risk_amount / risk_per_unit
        
        max_notional = capital * leverage
        max_size = max_notional / entry_price
        
        final_size = min(position_size, max_size)
        actual_risk = final_size * risk_per_unit
        
        return final_size, actual_risk

    def create_blueprint(
        self,
        decision: Decision,
        portfolio: PortfolioState,
        probability_report: ProbabilityReport,
        current_price: float,
        atr: float,
        structure_low: float | None = None,
        structure_high: float | None = None,
        ob_bot: float | None = None,
        ob_top: float | None = None,
        htf_high: float | None = None,
        htf_low: float | None = None,
    ) -> TradeBlueprint | None:
        """Create the complete trade execution blueprint."""
        
        if decision.decision_type != "TRADE":
            return None
            
        if atr <= 0 or current_price <= 0:
            return None

        stop_loss = self.compute_stop_loss(
            current_price, atr, decision.direction,
            structure_low, structure_high, ob_bot, ob_top
        )

        tp1, tp2, tp3, tp = self.compute_take_profit(
            current_price, stop_loss, decision.direction, htf_high, htf_low
        )

        position_size, risk_size = self.compute_position_size(
            portfolio.available_capital, current_price, stop_loss
        )

        if position_size <= 0:
            return None

        risk_pts = abs(current_price - stop_loss)
        reward_pts = abs(tp - current_price)
        rr = reward_pts / risk_pts if risk_pts > 0 else 0.0
        
        tqi = self._clamp(
            probability_report.probability_long * 0.30 +
            decision.confidence * 0.20 +
            probability_report.expected_value * 0.20 +
            (1.0 - probability_report.uncertainty) * 0.15 +
            self._clamp(rr / 3.0, 0.0, 1.0) * 0.15,
            0.0, 1.0
        )

        return TradeBlueprint(
            decision_id=decision.trace_id or str(uuid.uuid4()),
            symbol="BTC-SWAP-USDT",  # Hardcoded for test, will be dynamic in production
            exchange="toobit",
            direction=decision.direction,
            probability=probability_report.probability_long if decision.direction == "LONG" else probability_report.probability_short,
            confidence=decision.confidence,
            expected_value=probability_report.expected_value,
            position_size=position_size,
            risk_size=risk_size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=tp,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            trade_quality_index=tqi,
            risk_reward_ratio=rr
        )
