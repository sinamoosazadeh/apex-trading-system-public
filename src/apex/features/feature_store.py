"""Institutional Feature Store with Dependency Graph and 3-tier architecture."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict, deque
import time
import hashlib
import math
from enum import Enum

class FeatureCategory(Enum):
    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    TREND = "trend"
    MOMENTUM = "momentum"
    LIQUIDITY = "liquidity"

@dataclass(frozen=True)
class Feature:
    """Standardized feature object. Immutable and validated."""
    feature_id: str
    name: str
    category: FeatureCategory
    version: str = "1.0.0"
    value: float = 0.0
    normalized_value: float = 0.0
    confidence: float = 1.0
    reliability: float = 1.0
    quality: float = 1.0
    importance: float = 0.0
    weight: float = 0.0
    age: float = 0.0
    timestamp: float = field(default_factory=time.time)
    timeframe: str = "1m"
    symbol: str = ""
    exchange: str = ""
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    normalization_method: str = "zscore"
    calculation_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for val in [self.value, self.normalized_value, self.confidence, self.reliability, self.quality]:
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"Feature '{self.name}' contains NaN or Inf: {val}")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Feature confidence must be in [0, 1], got {self.confidence}")

    @property
    def hash(self) -> str:
        content = f"{self.name}:{self.version}:{self.value}:{self.timestamp}:{self.symbol}:{self.timeframe}"
        return hashlib.sha256(content.encode()).hexdigest()

class FeatureStore:
    """Three-tier feature store with dependency resolution."""

    def __init__(self, max_warm_size: int = 10000, max_cold_size: int = 100000) -> None:
        self._hot: dict[str, Feature] = {}
        self._warm: dict[str, deque[Feature]] = defaultdict(lambda: deque(maxlen=max_warm_size))
        self._cold: dict[str, list[Feature]] = defaultdict(list)
        self._max_cold_size = max_cold_size
        self._registry: dict[str, dict[str, Any]] = {}
        self._dependency_graph: dict[str, list[str]] = {}

    def _key(self, name: str, symbol: str, timeframe: str) -> str:
        return f"{name}:{symbol}:{timeframe}"

    def register(self, name: str, category: FeatureCategory, dependencies: list[str] = [], **meta: Any) -> None:
        self._registry[name] = {"category": category, "registered_at": time.time(), **meta}
        self._dependency_graph[name] = dependencies

    def are_dependencies_ready(self, name: str, symbol: str, timeframe: str, current_timestamp: float, max_age_sec: float = 60.0) -> bool:
        deps = self._dependency_graph.get(name, [])
        for dep_name in deps:
            key = self._key(dep_name, symbol, timeframe)
            feature = self._hot.get(key)
            if feature is None:
                return False
            if (current_timestamp - feature.timestamp) > max_age_sec:
                return False
        return True

    def store(self, feature: Feature) -> None:
        key = self._key(feature.name, feature.symbol, feature.timeframe)
        self._hot[key] = feature
        self._warm[key].append(feature)
        self._cold[key].append(feature)
        if len(self._cold[key]) > self._max_cold_size:
            self._cold[key].pop(0)

    def get(self, name: str, symbol: str = "", timeframe: str = "1m") -> Feature | None:
        return self._hot.get(self._key(name, symbol, timeframe))

    def get_history(self, name: str, symbol: str = "", timeframe: str = "1m", limit: int = 100) -> list[Feature]:
        key = self._key(name, symbol, timeframe)
        return list(self._warm[key])[-limit:]
