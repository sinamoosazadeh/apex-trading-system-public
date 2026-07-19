"""Tests for Data Platform - Phase 2."""
import pytest
import math
from apex.domain.market import MarketBar, Tick, OrderBook, OrderBookLevel
from apex.infrastructure.data_validator import DataValidator

def test_market_bar_validation_logic():
    bar = MarketBar(timestamp=1, open=100, high=110, low=90, close=105, volume=10)
    assert bar.range == 20
    assert bar.body == 5
    
    with pytest.raises(ValueError):
        MarketBar(timestamp=1, open=100, high=90, low=110, close=100)
        
    with pytest.raises(ValueError):
        MarketBar(timestamp=1, open=100, high=100, low=90, close=110)

def test_market_bar_nan_rejection():
    with pytest.raises(ValueError):
        MarketBar(timestamp=1, open=math.nan, high=110, low=90, close=105)

def test_orderbook_properties():
    bids = (OrderBookLevel(price=99.0, quantity=1.0),)
    asks = (OrderBookLevel(price=101.0, quantity=1.0),)
    book = OrderBook(timestamp=1, symbol="BTC", bids=bids, asks=asks)
    
    assert book.best_bid == 99.0
    assert book.best_ask == 101.0
    assert book.mid_price == 100.0
    assert book.spread == 2.0
    # 2.0 / 100.0 * 10000 = 200.0 bps
    assert book.spread_bps == 200.0

def test_data_validator_tick():
    validator = DataValidator()
    tick = Tick(timestamp=1, price=100, volume=1, side="buy")
    res = validator.validate_tick(tick)
    assert res.is_valid
    
    # Domain object itself should reject invalid side before validator
    with pytest.raises(ValueError):
        Tick(timestamp=1, price=100, volume=1, side="unknown")

def test_data_validator_crossed_orderbook():
    validator = DataValidator()
    bids = (OrderBookLevel(price=101.0, quantity=1.0),) # Bid > Ask
    asks = (OrderBookLevel(price=100.0, quantity=1.0),)
    book = OrderBook(timestamp=1, symbol="BTC", bids=bids, asks=asks)
    
    res = validator.validate_orderbook(book)
    assert not res.is_valid
    assert "Crossed orderbook" in res.errors[0]
