"""Crypto-Only - No Forex Sessions. 24/7 market."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class CryptoSession:
    is_active: bool = True
    reason: str = "Crypto market 24/7 - no session filter"
class SessionFilter:
    def is_trading_allowed(self, symbol: str) -> CryptoSession:
        return CryptoSession(True, "Crypto 24/7")
    def get_volatility_multiplier(self) -> float:
        return 1.0
SESSION_FILTER = SessionFilter()
