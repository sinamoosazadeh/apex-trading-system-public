
from __future__ import annotations
from typing import Dict, Any
import optuna

class SignalSearchSpace:
    """All Signal Parameters per blueprint Groups A-G - Modular, No Hardcode"""
    @staticmethod
    def define(trial: optuna.Trial) -> Dict[str, Any]:
        params = {}
        # Group A - Indicators
        params["ema_fast"] = trial.suggest_int("ema_fast", 5, 50)
        params["ema_slow"] = trial.suggest_int("ema_slow", 20, 200)
        params["atr_length"] = trial.suggest_int("atr_length", 7, 30)
        params["atr_multiplier"] = trial.suggest_float("atr_multiplier", 0.5, 3.0)
        params["rsi_length"] = trial.suggest_int("rsi_length", 7, 30)
        params["rsi_overbought"] = trial.suggest_int("rsi_overbought", 60, 85)
        params["rsi_oversold"] = trial.suggest_int("rsi_oversold", 15, 40)
        params["macd_fast"] = trial.suggest_int("macd_fast", 8, 20)
        params["macd_slow"] = trial.suggest_int("macd_slow", 20, 40)
        params["macd_signal"] = trial.suggest_int("macd_signal", 5, 15)
        params["bollinger_length"] = trial.suggest_int("bollinger_length", 10, 30)
        params["bollinger_std"] = trial.suggest_float("bollinger_std", 1.5, 3.0)
        params["supertrend_length"] = trial.suggest_int("supertrend_length", 7, 20)
        params["supertrend_factor"] = trial.suggest_float("supertrend_factor", 1.0, 5.0)
        params["adx_length"] = trial.suggest_int("adx_length", 10, 30)
        params["adx_threshold"] = trial.suggest_int("adx_threshold", 15, 35)

        # Group B - Candlestick
        params["body_ratio_min"] = trial.suggest_float("body_ratio_min", 0.3, 0.8)
        params["shadow_ratio_max"] = trial.suggest_float("shadow_ratio_max", 0.2, 0.6)
        params["engulf_threshold"] = trial.suggest_float("engulf_threshold", 0.8, 1.2)

        # Group C - Structure
        params["pivot_left"] = trial.suggest_int("pivot_left", 2, 10)
        params["pivot_right"] = trial.suggest_int("pivot_right", 2, 10)
        params["swing_sensitivity"] = trial.suggest_float("swing_sensitivity", 0.3, 1.5)
        params["bos_confirmation"] = trial.suggest_int("bos_confirmation", 1, 5)
        params["choch_confirmation"] = trial.suggest_int("choch_confirmation", 1, 5)
        params["structure_window"] = trial.suggest_int("structure_window", 20, 100)
        params["break_buffer_atr"] = trial.suggest_float("break_buffer_atr", 0.1, 1.0)

        # Group D - Liquidity
        params["eqh_equal_threshold"] = trial.suggest_float("eqh_equal_threshold", 0.0005, 0.005)
        params["liquidity_sweep_buffer"] = trial.suggest_float("liquidity_sweep_buffer", 0.1, 1.0)
        params["stop_hunt_buffer_atr"] = trial.suggest_float("stop_hunt_buffer_atr", 0.2, 1.5)

        # Group E - ICT
        params["fvg_min_size_atr"] = trial.suggest_float("fvg_min_size_atr", 0.2, 2.0)
        params["ob_lookback"] = trial.suggest_int("ob_lookback", 5, 50)
        params["breaker_lookback"] = trial.suggest_int("breaker_lookback", 10, 100)
        params["ote_fib_low"] = trial.suggest_float("ote_fib_low", 0.6, 0.75)
        params["ote_fib_high"] = trial.suggest_float("ote_fib_high", 0.75, 0.9)
        params["premium_discount_threshold"] = trial.suggest_float("premium_discount_threshold", 0.4, 0.6)

        # Group F - Evidence Weights (13 evidences) - will be normalized to sum 1
        raw_weights = {}
        for ev in ["momentum","structure","volume","volatility","order_flow","liquidity","ict","smt","regime","fvg","order_block","bos","market_structure"]:
            raw_weights[f"w_{ev}"] = trial.suggest_float(f"w_{ev}", 0.02, 0.3)
        # Normalize
        total = sum(raw_weights.values())
        for k,v in raw_weights.items():
            params[k] = v / total if total > 0 else 1/13

        # Group G - Probability
        params["bayesian_prior"] = trial.suggest_float("bayesian_prior", 0.3, 0.7)
        params["confidence_threshold"] = trial.suggest_float("confidence_threshold", 0.5, 0.85)
        params["min_probability"] = trial.suggest_float("min_probability", 0.5, 0.7)
        params["decision_threshold_long"] = trial.suggest_float("decision_threshold_long", 0.55, 0.75)
        params["decision_threshold_short"] = trial.suggest_float("decision_threshold_short", 0.55, 0.75)

        return params

    @staticmethod
    def default() -> Dict[str, Any]:
        # Default params per blueprint
        return {
            "ema_fast": 12, "ema_slow": 26, "atr_length": 14, "atr_multiplier": 1.5,
            "rsi_length": 14, "rsi_overbought": 70, "rsi_oversold": 30,
            "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
            "bollinger_length": 20, "bollinger_std": 2.0,
            "supertrend_length": 10, "supertrend_factor": 3.0,
            "adx_length": 14, "adx_threshold": 25,
            "body_ratio_min": 0.5, "shadow_ratio_max": 0.3, "engulf_threshold": 1.0,
            "pivot_left": 3, "pivot_right": 3, "swing_sensitivity": 0.5,
            "bos_confirmation": 2, "choch_confirmation": 2, "structure_window": 50, "break_buffer_atr": 0.3,
            "eqh_equal_threshold": 0.001, "liquidity_sweep_buffer": 0.5, "stop_hunt_buffer_atr": 0.5,
            "fvg_min_size_atr": 0.5, "ob_lookback": 20, "breaker_lookback": 30,
            "ote_fib_low": 0.62, "ote_fib_high": 0.79, "premium_discount_threshold": 0.5,
            "w_momentum": 0.1, "w_structure": 0.12, "w_volume": 0.07, "w_volatility": 0.06,
            "w_order_flow": 0.1, "w_liquidity": 0.1, "w_ict": 0.1, "w_smt": 0.05,
            "w_regime": 0.08, "w_fvg": 0.06, "w_order_block": 0.06, "w_bos": 0.05, "w_market_structure": 0.05,
            "bayesian_prior": 0.5, "confidence_threshold": 0.65, "min_probability": 0.6,
            "decision_threshold_long": 0.62, "decision_threshold_short": 0.62
        }
