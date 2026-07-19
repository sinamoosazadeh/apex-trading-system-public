"""Secure Config Manager - Crypto-Only - Fixed isinstance"""
from __future__ import annotations
import os
from .vault import Vault, ExchangeCredentials

class SecureConfigManager:
    def __init__(self, vault: Vault):
        self.vault = vault
        self._config = {}
    def load_from_env(self):
        api_key = os.getenv("TOOBIT_API_KEY")
        api_secret = os.getenv("TOOBIT_API_SECRET")
        if not api_key or not api_secret:
            raise ValueError("Missing TOOBIT_API_KEY or TOOBIT_API_SECRET")
        self._config["exchange"] = "toobit"
        self._config["symbols"] = os.getenv("APEX_SYMBOLS", "BTC-SWAP-USDT").split(",")
        self._config["credentials"] = self.vault.load_exchange_credentials("toobit", api_key, api_secret)
    def get(self, key: str):
        return self._config.get(key)

# Re-export for isinstance checks
ExchangeCredentials = ExchangeCredentials
