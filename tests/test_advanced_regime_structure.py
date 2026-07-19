"""Tests for Advanced Regime & Structure - Phase 14."""
import pytest
from apex.features.regime_engine import RegimeEngine
from apex.features.structure import update_structure, StructureState
from apex.domain.market import MarketBar

@pytest.fixture
def engine():
    return RegimeEngine(adx_len=14, er_len=20, rank_len=100)

def generate_bars(start_price: float, trend_pct: float, volatility_pct: float, count: int, base_vol: float = 100.0) -> list[MarketBar]:
    bars = []
    price = start_price
    for i in range(count):
        open_price = price
        close_price = price * (1.0 + trend_pct)
        high_price = max(open_price, close_price) * (1.0 + volatility_pct)
        low_price = min(open_price, close_price) * (1.0 - volatility_pct)
        volume = base_vol + (abs(trend_pct) * 1000) + (i % 5)
        bars.append(MarketBar(
            timestamp=float(i), open=open_price, high=high_price, low=low_price, close=close_price, volume=volume
        ))
        price = close_price
    return bars

def test_regime_strong_bull_trend(engine):
    bars = generate_bars(start_price=100.0, trend_pct=0.015, volatility_pct=0.005, count=150)
    regime = engine.detect_regime(bars)
    assert regime.trend_class in ["STRONG_BULL", "BULL"]
    assert regime.is_trending == True

def test_regime_strong_bear_trend(engine):
    bars = generate_bars(start_price=10000.0, trend_pct=-0.015, volatility_pct=0.005, count=150)
    regime = engine.detect_regime(bars)
    assert regime.trend_class in ["STRONG_BEAR", "BEAR"]

def test_regime_ranging_compression(engine):
    bars = generate_bars(start_price=100.0, trend_pct=0.0, volatility_pct=0.001, count=150)
    regime = engine.detect_regime(bars)
    assert regime.is_ranging == True
    assert regime.is_compression == True

def test_structure_sweep_detection():
    # Manually set state where the last Pivot High was 110.0
    state = StructureState(last_ph=110.0)
    
    # A new bar comes in: high sweeps 110 (goes to 115), but close is below 110 (at 100)
    highs = [115.0]
    lows = [99.0]
    closes = [100.0]
    
    state = update_structure(state, highs, lows, closes, atr=5.0, pivot_lb=2)
    
    assert state.sweep_high == True
