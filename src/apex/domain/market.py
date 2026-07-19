"""Market data domain objects with strict validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import math

@dataclass(frozen=True)
class Tick:
    """Individual market tick. Immutable and validated."""
    timestamp: float
    price: float
    volume: float
    side: str  # 'buy' or 'sell'
    trade_id: str = ""
    exchange: str = ""
    symbol: str = ""
    receive_time: float = 0.0
    sequence: int = 0
    quality_score: float = 1.0

    def __post_init__(self) -> None:
        if math.isnan(self.price) or math.isinf(self.price):
            raise ValueError(f"Tick price must be finite: {self.price}")
        if self.price <= 0:
            raise ValueError(f"Tick price must be positive: {self.price}")
        if math.isnan(self.volume) or math.isinf(self.volume):
            raise ValueError(f"Tick volume must be finite: {self.volume}")
        if self.volume < 0:
            raise ValueError(f"Tick volume cannot be negative: {self.volume}")
        if self.side not in ('buy', 'sell'):
            raise ValueError(f"Invalid tick side: {self.side}")

@dataclass(frozen=True)
class OrderBookLevel:
    """Single level in order book."""
    price: float
    quantity: float
    orders: int = 0

    def __post_init__(self) -> None:
        if math.isnan(self.price) or math.isinf(self.price):
            raise ValueError("OrderBookLevel price must be finite")
        if math.isnan(self.quantity) or math.isinf(self.quantity):
            raise ValueError("OrderBookLevel quantity must be finite")

@dataclass(frozen=True)
class OrderBook:
    """Order book snapshot. Immutable and validated."""
    timestamp: float
    symbol: str
    bids: tuple[OrderBookLevel, ...] = field(default_factory=tuple)
    asks: tuple[OrderBookLevel, ...] = field(default_factory=tuple)
    exchange: str = ""

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        if mid <= 0:
            return 0.0
        return (self.spread / mid) * 10000.0

    @property
    def bid_volume(self) -> float:
        return sum(level.quantity for level in self.bids[:20])

    @property
    def ask_volume(self) -> float:
        return sum(level.quantity for level in self.asks[:20])

    @property
    def imbalance(self) -> float:
        total = self.bid_volume + self.ask_volume
        if total == 0:
            return 0.0
        return (self.bid_volume - self.ask_volume) / total

@dataclass(frozen=True)
class MarketBar:
    """OHLCV candle bar. Immutable and validated."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    trades: int = 0
    vwap: float = 0.0
    spread: float = 0.0
    funding: float = 0.0
    open_interest: float = 0.0
    exchange: str = ""
    symbol: str = ""
    timeframe: str = "1m"
    quality_score: float = 1.0

    def __post_init__(self) -> None:
        # Numerical Stability Policy
        for val in [self.open, self.high, self.low, self.close, self.volume]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"MarketBar contains NaN or Inf: {self.symbol} {self.timestamp}")
        
        # Market Rule Validation
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) < Low ({self.low}) for {self.symbol}")
        if self.open < 0 or self.close < 0:
            raise ValueError("Price cannot be negative")
        if self.high < max(self.open, self.close):
            raise ValueError(f"High ({self.high}) < Open/Close ({self.open}/{self.close})")
        if self.low > min(self.open, self.close):
            raise ValueError(f"Low ({self.low}) > Open/Close ({self.open}/{self.close})")

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_frac(self) -> float:
        r = self.range
        return self.body / r if r > 0 else 0.0

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def close_location(self) -> float:
        r = self.range
        return (self.close - self.low) / r if r > 0 else 0.5

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def log_return(self) -> float:
        if self.open <= 0:
            return 0.0
        return math.log(self.close / self.open)
