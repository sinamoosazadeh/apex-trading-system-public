
"""Secure Config Manager - Full Implementation - Crypto-Only"""
from __future__ import annotations
import os
from typing import Dict, Any
from .vault import Vault
from .contracts import ExchangeCredentials

class SecureConfigManager:
    """Manages secure configuration with Vault encryption"""
    def __init__(self, vault: Vault):
        self.vault = vault
        self._config: Dict[str, Any] = {}
    
    def load_from_env(self):
        api_key = os.getenv("TOOBIT_API_KEY")
        api_secret = os.getenv("TOOBIT_API_SECRET")
        if not api_key or not api_secret:
            raise ValueError("Missing TOOBIT_API_KEY or TOOBIT_API_SECRET")
        self._config["exchange"] = "toobit"
        self._config["symbols"] = os.getenv("APEX_SYMBOLS", "BTC-SWAP-USDT,ETH-SWAP-USDT,SOL-SWAP-USDT,XRP-SWAP-USDT,BNB-SWAP-USDT,DOGE-SWAP-USDT,ADA-SWAP-USDT,AVAX-SWAP-USDT,LINK-SWAP-USDT,DOT-SWAP-USDT").split(",")
        self._config["timeframes"] = os.getenv("APEX_TIMEFRAMES", "1m,3m,5m,15m,30m,1h,2h,4h,6h,12h,1d,3d,1w,1M").split(",")
        self._config["credentials"] = self.vault.load_exchange_credentials("toobit", api_key, api_secret)
        self._config["mode"] = "crypto-only-24-7"
    
    def get(self, key: str):
        return self._config.get(key)
    
    def get_all(self) -> Dict[str, Any]:
        return self._config.copy()
    
    def secure_boot_check(self) -> bool:
        return "exchange" in self._config and "credentials" in self._config and self._config.get("mode") == "crypto-only-24-7"

# Re-export for isinstance checks
ExchangeCredentials = ExchangeCredentials
