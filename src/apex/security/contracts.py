"""Security domain objects and contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SecureString:
    """Wrapper for sensitive strings to prevent accidental logging."""
    _encrypted_value: bytes
    _vault_key: bytes

    def __post_init__(self) -> None:
        if not self._encrypted_value or not self._vault_key:
            raise ValueError("SecureString requires encrypted value and vault key")

    def decrypt(self) -> str:
        """Decrypt the string in memory."""
        from cryptography.fernet import Fernet
        f = Fernet(self._vault_key)
        return f.decrypt(self._encrypted_value).decode('utf-8')

    def __repr__(self) -> str:
        return "SecureString(***)"

    def __str__(self) -> str:
        return "***"

@dataclass(frozen=True)
class ExchangeCredentials:
    """Exchange API credentials."""
    exchange: str
    api_key: SecureString
    api_secret: SecureString
    
    def __repr__(self) -> str:
        return f"ExchangeCredentials(exchange={self.exchange}, api_key=***, api_secret=***)"
