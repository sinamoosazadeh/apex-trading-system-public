"""Primitive feature calculations with numerical stability guarantees."""
from __future__ import annotations

import math
from typing import Sequence
import time

from ..domain.market import MarketBar
from .feature_store import Feature, FeatureStore, FeatureCategory

class PrimitiveFeatures:
    """Calculates base features from raw market data."""

    def __init__(self, store: FeatureStore) -> None:
        self.store = store
        self.store.register("ATR", FeatureCategory.VOLATILITY, dependencies=[])
        self.store.register("RSI", FeatureCategory.MOMENTUM, dependencies=[])

    def calculate_atr(self, bars: Sequence[MarketBar], period: int = 14, symbol: str = "", timeframe: str = "1m") -> Feature:
        """Average True Range with Wilder's Smoothing. No NaN propagation."""
        if len(bars) < period + 1:
            value = 0.0
            confidence = 0.0
        else:
            trs = []
            for i in range(1, len(bars)):
                bar = bars[i]
                prev_close = bars[i-1].close
                tr = max(
                    bar.high - bar.low,
                    abs(bar.high - prev_close),
                    abs(bar.low - prev_close)
                )
                trs.append(tr)
            
            atr = sum(trs[:period]) / period
            for i in range(period, len(trs)):
                atr = (atr * (period - 1) + trs[i]) / period
            
            if math.isnan(atr) or math.isinf(atr) or atr <= 0:
                value = 0.0
                confidence = 0.1
            else:
                value = atr
                confidence = 1.0

        feature = Feature(
            feature_id=f"ATR_{symbol}_{timeframe}_{int(time.time())}",
            name="ATR",
            category=FeatureCategory.VOLATILITY,
            value=value,
            confidence=confidence,
            symbol=symbol,
            timeframe=timeframe,
            dependencies=(),
            metadata={"period": period}
        )
        self.store.store(feature)
        return feature

    def calculate_rsi(self, bars: Sequence[MarketBar], period: int = 14, symbol: str = "", timeframe: str = "1m") -> Feature:
        """Relative Strength Index with division-by-zero protection."""
        if len(bars) < period + 1:
            value = 50.0
            confidence = 0.0
        else:
            gains = []
            losses = []
            for i in range(1, len(bars)):
                diff = bars[i].close - bars[i-1].close
                gains.append(max(0.0, diff))
                losses.append(max(0.0, -diff))

            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period

            for i in range(period, len(gains)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            if avg_loss == 0:
                value = 100.0 if avg_gain > 0 else 50.0
            else:
                rs = avg_gain / avg_loss
                value = 100.0 - (100.0 / (1.0 + rs))
            
            if math.isnan(value) or math.isinf(value):
                value = 50.0
                confidence = 0.1
            else:
                confidence = 1.0

        feature = Feature(
            feature_id=f"RSI_{symbol}_{timeframe}_{int(time.time())}",
            name="RSI",
            category=FeatureCategory.MOMENTUM,
            value=value,
            confidence=confidence,
            symbol=symbol,
            timeframe=timeframe,
            dependencies=(),
            metadata={"period": period}
        )
        self.store.store(feature)
        return feature
