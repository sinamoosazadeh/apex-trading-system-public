"""Tests for Feature Platform - Phase 3."""
import pytest
import math
from apex.features.feature_store import FeatureStore, Feature, FeatureCategory
from apex.features.primitives import PrimitiveFeatures
from apex.domain.market import MarketBar

@pytest.fixture
def sample_bars():
    bars = []
    price = 100.0
    for i in range(20):
        bars.append(MarketBar(
            timestamp=float(i),
            open=price,
            high=price + (i % 3) + 1,
            low=price - (i % 2) - 1,
            close=price + (i % 2),
            volume=10.0 * (i + 1)
        ))
        price += 0.5
    return bars

def test_feature_store_dependency_graph():
    store = FeatureStore()
    store.register("RSI", FeatureCategory.MOMENTUM, dependencies=[])
    store.register("RSI_SMA", FeatureCategory.MOMENTUM, dependencies=["RSI"])
    
    assert not store.are_dependencies_ready("RSI_SMA", "BTC", "1m", current_timestamp=10.0)
    
    # اصلاح: افزودن symbol و timeframe به فیچر
    rsi_feat = Feature(feature_id="1", name="RSI", category=FeatureCategory.MOMENTUM, timestamp=10.0, symbol="BTC", timeframe="1m")
    store.store(rsi_feat)
    
    assert store.are_dependencies_ready("RSI_SMA", "BTC", "1m", current_timestamp=10.0)
    assert not store.are_dependencies_ready("RSI_SMA", "BTC", "1m", current_timestamp=100.0, max_age_sec=10.0)

def test_primitive_features_atr(sample_bars):
    store = FeatureStore()
    engine = PrimitiveFeatures(store)
    
    atr = engine.calculate_atr(sample_bars, period=14, symbol="BTC", timeframe="1m")
    
    assert atr.name == "ATR"
    assert atr.value > 0
    assert atr.confidence == 1.0
    assert not math.isnan(atr.value)
    
    retrieved = store.get("ATR", "BTC", "1m")
    assert retrieved is not None
    assert retrieved.value == atr.value

def test_primitive_features_rsi_division_by_zero():
    store = FeatureStore()
    engine = PrimitiveFeatures(store)
    
    flat_bars = [
        MarketBar(timestamp=float(i), open=100, high=100, low=100, close=100)
        for i in range(20)
    ]
    
    rsi = engine.calculate_rsi(flat_bars, period=14, symbol="ETH", timeframe="1m")
    
    assert rsi.value == 50.0
    assert rsi.confidence == 1.0

def test_feature_immutability_and_nan_rejection():
    with pytest.raises(ValueError):
        Feature(
            feature_id="1",
            name="TEST",
            category=FeatureCategory.PRICE,
            value=float('nan')
        )
