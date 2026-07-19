
"""Core Types - Institutional - Crypto-Only - Full Implementation"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum

# Import enums
from .enums import EventType, OrderStatus, DecisionType, Direction, RegimeType

# Re-export domain contracts for easy access
try:
    from ...domain.market import MarketBar, Tick, OrderBook
    from ...domain.trading import Position, Trade, Order, OrderSide, OrderType
except ImportError:
    # Fallback for direct import
    MarketBar = None
    Tick = None

# Core Value Objects per blueprints
@dataclass(frozen=True)
class Price:
    """Immutable price value object with validation per blueprints"""
    value: float
    symbol: str
    
    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"Price must be > 0, got {self.value}")
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
        # NaN rejection per blueprints
        import math
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Price cannot be NaN or Inf: {self.value}")

@dataclass(frozen=True)
class Quantity:
    """Immutable quantity value object"""
    value: float
    
    def __post_init__(self):
        if self.value <= 0:
            raise ValueError(f"Quantity must be > 0, got {self.value}")
        import math
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Quantity cannot be NaN or Inf")

@dataclass(frozen=True)
class Percentage:
    """Percentage with bounds checking 0-100% per blueprints"""
    value: float
    
    def __post_init__(self):
        if not 0 <= self.value <= 1:
            raise ValueError(f"Percentage must be 0-1, got {self.value}")

# Probability types per blueprints
@dataclass
class ProbabilityDistribution:
    """Bayesian probability distribution - sums to 1 per blueprints"""
    long: float
    short: float
    no_trade: float
    
    def __post_init__(self):
        total = self.long + self.short + self.no_trade
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"Probabilities must sum to 1, got {total}")
        for v in [self.long, self.short, self.no_trade]:
            if not 0 <= v <= 1:
                raise ValueError(f"Probability must be 0-1, got {v}")

@dataclass
class ConfidenceInterval:
    """Confidence interval for predictions"""
    lower: float
    upper: float
    confidence: float = 0.95
    
    def __post_init__(self):
        if self.lower > self.upper:
            raise ValueError("Lower must be <= upper")

# Evidence types - 13 institutional evidences per blueprints
class EvidenceType(str, Enum):
    MOMENTUM = "momentum"
    STRUCTURE = "structure"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    ORDER_FLOW = "order_flow"
    LIQUIDITY = "liquidity"
    ICT = "ict"
    SMT = "smt"
    REGIME = "regime"
    FVG = "fvg"
    ORDER_BLOCK = "order_block"
    BREAK_OF_STRUCTURE = "bos"
    MARKET_STRUCTURE = "market_structure"

@dataclass
class Evidence:
    """Single evidence result per blueprints"""
    type: EvidenceType
    long_score: float  # 0-1
    short_score: float  # 0-1
    confidence: float  # 0-1
    weight: float = 1.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        for field in [self.long_score, self.short_score, self.confidence]:
            if not 0 <= field <= 1:
                raise ValueError(f"Evidence scores must be 0-1, got {field}")

# Risk types
@dataclass
class RiskLimits:
    """Portfolio risk limits per blueprints"""
    max_position_size: float = 0.1  # 10% per position
    max_total_exposure: float = 0.3  # 30% total
    max_daily_loss: float = 0.05  # 5% daily
    max_drawdown: float = 0.15  # 15% max DD
    risk_per_trade: float = 0.01  # 1% per trade

# Timeframe type - 14 timeframes per blueprints (crypto-only)
class Timeframe(str, Enum):
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H12 = "12h"
    D1 = "1d"
    D3 = "3d"
    W1 = "1w"
    M1M = "1M"
    
    @classmethod
    def all_14(cls) -> List[str]:
        return [tf.value for tf in cls]
    
    @classmethod
    def is_valid(cls, tf: str) -> bool:
        return tf in cls.all_14()

# Symbol type - 10 Toobit top coins per blueprints (crypto-only, no forex)
class CryptoSymbol(str, Enum):
    BTC = "BTC-SWAP-USDT"
    ETH = "ETH-SWAP-USDT"
    SOL = "SOL-SWAP-USDT"
    XRP = "XRP-SWAP-USDT"
    BNB = "BNB-SWAP-USDT"
    DOGE = "DOGE-SWAP-USDT"
    ADA = "ADA-SWAP-USDT"
    AVAX = "AVAX-SWAP-USDT"
    LINK = "LINK-SWAP-USDT"
    DOT = "DOT-SWAP-USDT"
    
    @classmethod
    def all_10(cls) -> List[str]:
        return [s.value for s in cls]

# Export all
__all__ = [
    # Enums from enums.py
    "EventType", "OrderStatus", "DecisionType", "Direction", "RegimeType",
    # Value objects
    "Price", "Quantity", "Percentage",
    # Probability
    "ProbabilityDistribution", "ConfidenceInterval",
    # Evidence
    "EvidenceType", "Evidence",
    # Risk
    "RiskLimits",
    # Timeframe & Symbol
    "Timeframe", "CryptoSymbol",
]
