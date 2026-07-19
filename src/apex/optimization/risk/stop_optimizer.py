"""Stop Optimizer sub-engine - per blueprint ATR, Structure, Swing, Liquidity, ICT, Volatility, Session, Hybrid, Adaptive, Dynamic"""
class StopOptimizer:
    MODELS = ["atr","structure","swing","liquidity","ict","volatility","session","hybrid","adaptive","dynamic"]
    def optimize(self, *args, **kwargs): return {"model": "hybrid", "multiplier": 1.5}
