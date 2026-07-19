
from __future__ import annotations
from typing import Dict, Any
import optuna

class RiskSearchSpace:
    """Per blueprint Part 6 - Risk & Execution Search Space"""
    @staticmethod
    def define(trial: optuna.Trial) -> Dict[str, Any]:
        params = {}
        # Entry Models
        params["entry_model"] = trial.suggest_categorical("entry_model", ["market","limit","pullback","liquidity_retest","order_block","fvg","breakout","confirmation","hybrid"])
        params["entry_offset_atr"] = trial.suggest_float("entry_offset_atr", 0.0, 1.0)
        params["entry_timing"] = trial.suggest_categorical("entry_timing", ["immediate","confirmed","retest"])

        # Stop Models per blueprint: ATR, Structure, Swing, Liquidity, ICT, Volatility, Session, Hybrid, Adaptive, Dynamic, AI Selected
        params["stop_model"] = trial.suggest_categorical("stop_model", ["atr","structure","swing","liquidity","ict","volatility","session","hybrid","adaptive","dynamic"])
        params["atr_stop_period"] = trial.suggest_int("atr_stop_period", 7, 30)
        params["atr_stop_multiplier"] = trial.suggest_float("atr_stop_multiplier", 1.0, 4.0)
        params["structure_buffer_atr"] = trial.suggest_float("structure_buffer_atr", 0.1, 1.0)
        params["swing_depth"] = trial.suggest_int("swing_depth", 2, 10)
        params["liquidity_offset_atr"] = trial.suggest_float("liquidity_offset_atr", 0.2, 1.5)
        params["min_stop_distance_atr"] = trial.suggest_float("min_stop_distance_atr", 0.3, 1.0)
        params["max_stop_distance_atr"] = trial.suggest_float("max_stop_distance_atr", 1.5, 5.0)
        params["adaptive_multiplier"] = trial.suggest_float("adaptive_multiplier", 0.8, 1.5)

        # Dynamic Stop Engine: Initial -> BE -> ATR Trail -> Structure Trail -> Liquidity Trail -> Emergency Trail
        params["be_trigger_rr"] = trial.suggest_float("be_trigger_rr", 0.8, 2.0)
        params["atr_trail_multiplier"] = trial.suggest_float("atr_trail_multiplier", 1.0, 3.5)
        params["structure_trail_buffer"] = trial.suggest_float("structure_trail_buffer", 0.1, 0.8)
        params["liquidity_trail_buffer"] = trial.suggest_float("liquidity_trail_buffer", 0.1, 1.0)
        params["emergency_trail_atr"] = trial.suggest_float("emergency_trail_atr", 2.0, 6.0)

        # Take Profit Models per blueprint
        params["tp_model"] = trial.suggest_categorical("tp_model", ["fixed_rr","liquidity","ict","order_block","fvg","swing","atr_projection","volatility_projection","adaptive","hybrid","multiple"])
        params["tp1_rr"] = trial.suggest_float("tp1_rr", 0.8, 2.0)
        params["tp2_rr"] = trial.suggest_float("tp2_rr", 1.5, 4.0)
        params["tp3_rr"] = trial.suggest_float("tp3_rr", 2.5, 8.0)
        params["tp4_rr"] = trial.suggest_float("tp4_rr", 4.0, 12.0)
        params["tp5_rr"] = trial.suggest_float("tp5_rr", 6.0, 20.0)
        params["tp1_allocation"] = trial.suggest_float("tp1_allocation", 0.2, 0.6)
        params["tp2_allocation"] = trial.suggest_float("tp2_allocation", 0.15, 0.4)
        params["tp3_allocation"] = trial.suggest_float("tp3_allocation", 0.1, 0.3)
        # Normalize allocations to sum 1
        total_alloc = params["tp1_allocation"] + params["tp2_allocation"] + params["tp3_allocation"]
        params["tp1_allocation"] /= total_alloc * 1.3  # leave room for tp4/5
        params["tp2_allocation"] /= total_alloc * 1.3
        params["tp3_allocation"] /= total_alloc * 1.3
        params["tp4_allocation"] = trial.suggest_float("tp4_allocation", 0.05, 0.2)
        params["tp5_allocation"] = trial.suggest_float("tp5_allocation", 0.02, 0.15)
        # Renormalize all 5
        total5 = sum(params[f"tp{i}_allocation"] for i in range(1,6))
        for i in range(1,6):
            params[f"tp{i}_allocation"] /= total5

        params["liquidity_target_buffer"] = trial.suggest_float("liquidity_target_buffer", 0.0, 0.5)
        params["ict_target_mode"] = trial.suggest_categorical("ict_target_mode", ["premium_discount","ote","liquidity"])

        # Position Sizing Models per blueprint
        params["sizing_model"] = trial.suggest_categorical("sizing_model", ["fixed_risk","atr_risk","volatility_risk","kelly","half_kelly","fractional_kelly","drawdown_adjusted","confidence_adjusted","probability_adjusted","portfolio_adjusted","correlation_adjusted","hybrid","adaptive"])
        params["risk_per_trade"] = trial.suggest_float("risk_per_trade", 0.003, 0.03)
        params["kelly_fraction"] = trial.suggest_float("kelly_fraction", 0.1, 0.5)
        params["kelly_lookback"] = trial.suggest_int("kelly_lookback", 20, 100)
        params["volatility_adjustment"] = trial.suggest_float("volatility_adjustment", 0.5, 1.5)
        params["confidence_adjustment_factor"] = trial.suggest_float("confidence_adjustment_factor", 0.5, 1.5)
        params["drawdown_adjustment_factor"] = trial.suggest_float("drawdown_adjustment_factor", 0.3, 1.0)

        # Portfolio Risk per blueprint
        params["max_daily_risk"] = trial.suggest_float("max_daily_risk", 0.02, 0.1)
        params["max_weekly_risk"] = trial.suggest_float("max_weekly_risk", 0.05, 0.2)
        params["max_monthly_risk"] = trial.suggest_float("max_monthly_risk", 0.1, 0.3)
        params["max_symbol_exposure"] = trial.suggest_float("max_symbol_exposure", 0.05, 0.3)
        params["max_correlation"] = trial.suggest_float("max_correlation", 0.5, 0.9)
        params["max_simultaneous_trades"] = trial.suggest_int("max_simultaneous_trades", 1, 5)
        params["max_floating_dd"] = trial.suggest_float("max_floating_dd", 0.05, 0.2)
        params["max_consecutive_losses"] = trial.suggest_int("max_consecutive_losses", 3, 10)
        params["max_leverage"] = trial.suggest_float("max_leverage", 1.0, 10.0)

        # Execution Models
        params["execution_model"] = trial.suggest_categorical("execution_model", ["market","limit","post_only","ioc","fok","twap","vwap","adaptive","liquidity_sensitive","spread_aware","latency_aware"])
        params["slippage_protection"] = trial.suggest_float("slippage_protection", 0.0001, 0.005)
        params["spread_threshold"] = trial.suggest_float("spread_threshold", 0.0005, 0.005)

        # Time Exit & Emergency
        params["time_exit_bars"] = trial.suggest_int("time_exit_bars", 20, 200)
        params["time_exit_profit_only"] = trial.suggest_categorical("time_exit_profit_only", [True, False])

        return params

    @staticmethod
    def default() -> Dict[str, Any]:
        return {
            "entry_model": "liquidity_retest", "entry_offset_atr": 0.2, "entry_timing": "retest",
            "stop_model": "hybrid", "atr_stop_period": 14, "atr_stop_multiplier": 1.5,
            "structure_buffer_atr": 0.3, "swing_depth": 3, "liquidity_offset_atr": 0.5,
            "min_stop_distance_atr": 0.5, "max_stop_distance_atr": 3.0, "adaptive_multiplier": 1.0,
            "be_trigger_rr": 1.0, "atr_trail_multiplier": 2.0, "structure_trail_buffer": 0.3,
            "liquidity_trail_buffer": 0.5, "emergency_trail_atr": 4.0,
            "tp_model": "liquidity", "tp1_rr": 1.0, "tp2_rr": 2.0, "tp3_rr": 3.5, "tp4_rr": 5.0, "tp5_rr": 8.0,
            "tp1_allocation": 0.4, "tp2_allocation": 0.25, "tp3_allocation": 0.2, "tp4_allocation": 0.1, "tp5_allocation": 0.05,
            "liquidity_target_buffer": 0.1, "ict_target_mode": "liquidity",
            "sizing_model": "half_kelly", "risk_per_trade": 0.01, "kelly_fraction": 0.25,
            "kelly_lookback": 50, "volatility_adjustment": 1.0, "confidence_adjustment_factor": 1.0,
            "drawdown_adjustment_factor": 0.7,
            "max_daily_risk": 0.05, "max_weekly_risk": 0.1, "max_monthly_risk": 0.15,
            "max_symbol_exposure": 0.15, "max_correlation": 0.7, "max_simultaneous_trades": 3,
            "max_floating_dd": 0.1, "max_consecutive_losses": 5, "max_leverage": 3.0,
            "execution_model": "adaptive", "slippage_protection": 0.001, "spread_threshold": 0.002,
            "time_exit_bars": 100, "time_exit_profit_only": False
        }
