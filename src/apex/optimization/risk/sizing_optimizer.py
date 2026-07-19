"""Sizing Optimizer sub-engine - Kelly, Half Kelly, etc"""
class SizingOptimizer:
    MODELS = ["fixed_risk","atr_risk","volatility_risk","kelly","half_kelly","fractional_kelly","drawdown_adjusted","confidence_adjusted","portfolio_adjusted"]
    def optimize(self, *args, **kwargs): return {"sizing_model": "half_kelly", "risk": 0.01}
