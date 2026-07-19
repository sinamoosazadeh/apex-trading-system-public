
"""APEX Exception Hierarchy - Book III 4.25"""
from __future__ import annotations

class APEXException(Exception):
    """Base exception with error code."""
    def __init__(self, message: str, code: str = "APEX-000", context: dict | None = None):
        super().__init__(message)
        self.code = code
        self.context = context or {}

class DataException(APEXException): pass
class MarketException(DataException): pass
class FeatureException(APEXException): pass
class ProbabilityException(APEXException): pass
class SignalException(APEXException): pass
class RiskException(APEXException): code_prefix = "RSK"
class ExecutionException(APEXException): code_prefix = "EXE"
class PortfolioException(APEXException): pass
class StorageException(APEXException): pass
class OptimizerException(APEXException): pass
class ResearchException(APEXException): pass
class SecurityException(APEXException): pass
class ValidationException(DataException): pass
class ConfigurationException(APEXException): pass
class ExchangeException(APEXException): pass
class ToobitClientError(ExchangeException):
    def __init__(self, code: int, msg: str):
        super().__init__(f"Toobit error {code}: {msg}", code=f"EXC-{code}")
        self.code = code
        self.msg = msg

