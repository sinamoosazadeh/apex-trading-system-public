"""Tests for Institutional Feature Engines - Phase 13."""
import pytest
import math
from apex.features.order_flow_engine import OrderFlowEngine
from apex.domain.market import Tick, OrderBook, OrderBookLevel
from apex.features.smt_engine import SMTPivots, evaluate_smt, SMT_CLASSIC, SMT_LIQUIDITY

@pytest.fixture
def of_engine():
    return OrderFlowEngine("BTC-SWAP-USDT", delta_window=10, avg_vol_window=10)

@pytest.fixture
def sample_book():
    bids = (OrderBookLevel(price=99.0, quantity=10.0), OrderBookLevel(price=98.0, quantity=5.0))
    asks = (OrderBookLevel(price=101.0, quantity=20.0), OrderBookLevel(price=102.0, quantity=5.0))
    return OrderBook(timestamp=1, symbol="BTC-SWAP-USDT", bids=bids, asks=asks)

def test_order_flow_delta_and_cvd(of_engine):
    of_engine.process_tick(Tick(timestamp=1, price=100, volume=5.0, side="buy"))
    of_engine.process_tick(Tick(timestamp=2, price=100, volume=3.0, side="buy"))
    of_engine.process_tick(Tick(timestamp=3, price=99, volume=4.0, side="sell"))
    
    state = of_engine.get_state()
    
    assert state.buy_volume == 8.0
    assert state.sell_volume == 4.0
    assert state.delta == 4.0
    assert state.cumulative_delta == 4.0
    assert state.aggression_ratio > 0.0

def test_order_flow_book_imbalance(of_engine, sample_book):
    of_engine.process_orderbook(sample_book)
    # Must process at least one tick for state to generate
    of_engine.process_tick(Tick(timestamp=1, price=100, volume=1.0, side="buy"))
    
    state = of_engine.get_state()
    
    # Bid Vol = 15, Ask Vol = 25 -> Total = 40 -> (15-25)/40 = -0.25
    assert state.book_imbalance == pytest.approx(-0.25)
    
    # Micro Price: (99 * 25 + 101 * 15) / 40 = (2475 + 1515) / 40 = 99.75
    assert state.micro_price == pytest.approx(99.75)

def test_order_flow_absorption_detection(of_engine):
    for i in range(10):
        of_engine.process_tick(Tick(timestamp=float(i), price=100, volume=2.0, side="buy"))
    
    state_normal = of_engine.get_state()
    assert state_normal.absorption_score < 0.5
    
    # Inject a massive volume tick with tiny price movement
    of_engine.process_tick(Tick(timestamp=11.0, price=100.01, volume=10.0, side="buy"))
    
    state_absorption = of_engine.get_state()
    assert state_absorption.absorption_score > 0.5

def test_smt_engine_classic_bull_divergence():
    # Manually inject pivots to test SMT logic directly
    # Chart makes lower low (100 -> 99), Ref makes higher low (101 -> 102)
    chart_pivots = SMTPivots(lp=99, pp=100, lh=107, phh=106, pl_age=1, ph_age=1)
    ref_pivots = SMTPivots(lp=102, pp=101, lh=107, phh=106, pl_age=1, ph_age=1)
    
    context = {
        "liq_l": 0.8, "liq_s": 0.1, "sweep_l": 0.7, "sweep_s": 0.1,
        "struct_l": 0.6, "struct_s": 0.2, "trend_l": 0.5, "trend_s": 0.2,
        "candle_l": 0.6, "candle_s": 0.2, "stop_l": 0.0, "stop_s": 0.0,
        "fvg_l": 0.0, "fvg_s": 0.0, "ob_l": 0.0, "ob_s": 0.0,
        "pd_l": 0.0, "pd_s": 0.0
    }
    
    bull_score, bear_score, bull_type, bear_type = evaluate_smt(
        enabled=True, corr_q=0.8, chart_pivots=chart_pivots, ref_pivots=ref_pivots,
        context_scores=context
    )
    
    assert bull_score > 0
    assert bear_score == 0
    # Should classify as Classic or Liquidity (since sweep_l > 0.35)
    assert bull_type in [SMT_CLASSIC, SMT_LIQUIDITY]
