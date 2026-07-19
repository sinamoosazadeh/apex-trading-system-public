
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import hashlib, json, uuid

from .optimization_state import OptimizerType

@dataclass
class ParameterPackage:
    package_id: str
    version: str
    symbol: str
    timeframe: str
    optimizer_type: OptimizerType
    market_regime: str = "all"
    optimizer_version: str = "1.0.0"
    blueprint_version: str = "APEX v4"
    git_revision: str = "unknown"
    dataset_hash: str = ""
    configuration_hash: str = ""
    creation_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_time: Optional[str] = None
    approval_time: Optional[str] = None
    expiration_time: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Optional[Dict[str, Any]] = None
    validation_results: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    status: str = "created"  # created, validated, approved, active, rejected, archived
    parent_version: Optional[str] = None
    changelog: str = ""
    optimization_method: str = "optuna_tpe"
    n_trials: int = 0
    history: list = field(default_factory=list)

    def __post_init__(self):
        if not self.expiration_time:
            self.expiration_time = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        if not self.checksum:
            self.checksum = self.compute_checksum()

    def compute_checksum(self) -> str:
        data = json.dumps(self.parameters, sort_keys=True, default=str)
        data += f"{self.symbol}{self.timeframe}{self.version}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def compute_dataset_hash(self, candles: list = None) -> str:
        if candles is None:
            return self.dataset_hash
        # Simple hash of first/last timestamp and count
        raw = f"{len(candles)}_{candles[0] if candles else ''}_{candles[-1] if candles else ''}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_valid_for(self, symbol: str, timeframe: str) -> bool:
        # Never Mix Coins/Timeframes - per blueprint
        return self.symbol == symbol and self.timeframe == timeframe

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create_new(cls, symbol: str, timeframe: str, optimizer_type: OptimizerType, parameters: Dict[str, Any], metrics=None, validation=None, parent_version=None, n_trials=0, method="optuna_tpe") -> "ParameterPackage":
        now = datetime.now(timezone.utc)
        pkg_id = f"{symbol}_{timeframe}_{optimizer_type.value}_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        version = f"{now.strftime('%Y.%m.%d')}.{uuid.uuid4().hex[:4]}"
        obj = cls(
            package_id=pkg_id,
            version=version,
            symbol=symbol,
            timeframe=timeframe,
            optimizer_type=optimizer_type,
            parameters=parameters,
            metrics=metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics,
            validation_results=validation or {},
            parent_version=parent_version,
            n_trials=n_trials,
            optimization_method=method,
        )
        obj.checksum = obj.compute_checksum()
        return obj
