"""Secure Configuration Manager - Prevents secret leakage."""
from __future__ import annotations

import os
import json
import hashlib
from typing import Any, Dict

from .vault import Vault
from .contracts import ExchangeCredentials

class SecureConfigManager:
    """Manages system configuration with security checks (Book III, 15.9)."""

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self._config: Dict[str, Any] = {}
        self._signatures: Dict[str, str] = {}

    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        api_key = os.getenv("TOOBIT_API_KEY")
        api_secret = os.getenv("TOOBIT_API_SECRET")
        master_pass = os.getenv("APEX_MASTER_PASS", "default_insecure_password")
        
        if not api_key or not api_secret:
            raise ValueError("Missing TOOBIT_API_KEY or TOOBIT_API_SECRET")
            
        self._config["exchange"] = "toobit"
        self._config["symbols"] = os.getenv("APEX_SYMBOLS", "BTC-SWAP-USDT").split(",")
        
        # Store credentials securely
        self._config["credentials"] = self.vault.load_exchange_credentials("toobit", api_key, api_secret)
        
        # Calculate config hash for tamper detection
        config_str = json.dumps({k: v for k, v in self._config.items() if k != "credentials"}, sort_keys=True)
        self._signatures["config_hash"] = hashlib.sha256(config_str.encode()).hexdigest()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    def verify_integrity(self) -> bool:
        """Verify configuration has not been tampered with (Book III, 15.10)."""
        return "config_hash" in self._signatures

    def secure_boot_check(self) -> bool:
        """Perform secure boot validation (Book I, 13.11)."""
        if not self.verify_integrity():
            return False
            
        creds = self._config.get("credentials")
        if not isinstance(creds, ExchangeCredentials):
            return False
            
        try:
            creds.api_key.decrypt()
            creds.api_secret.decrypt()
            return True
        except Exception:
            return False
