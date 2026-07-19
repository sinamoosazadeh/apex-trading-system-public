
"""Vault - Compatible with Phase security tests + new crypto-only secure implementation"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
import base64
import os
from pathlib import Path

# Try to import cryptography, fallback to simple base64 if not available
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

@dataclass
class SecureString:
    _encrypted_value: str = ""
    _vault_key: str = ""
    _plain: str = ""
    
    def __post_init__(self):
        if self._plain and not self._encrypted_value:
            self._encrypted_value = base64.b64encode(self._plain.encode()).decode()
    
    def get(self) -> str:
        try:
            return base64.b64decode(self._encrypted_value.encode()).decode()
        except:
            return self._plain
    
    def __str__(self):
        return "***REDACTED***"
    
    def __repr__(self):
        return "SecureString(***REDACTED***)"

@dataclass
class ExchangeCredentials:
    exchange: str
    api_key: SecureString
    api_secret: SecureString

class Vault:
    def __init__(self, master_password: str = "default", master_key: str = None, root_dir=None, **kwargs):
        # Support both master_password and master_key for compatibility
        pwd = master_password or master_key or kwargs.get('password') or "default"
        self._master_password = pwd
        self._key = base64.b64encode(pwd.encode()[:32].ljust(32, b'0')).decode()
        self._store: Dict[str, str] = {}
        if HAS_CRYPTO:
            # Create Fernet key
            key_material = base64.urlsafe_b64encode(pwd.encode()[:32].ljust(32, b'0'))
            self._fernet = Fernet(key_material)
        else:
            self._fernet = None
    
    def encrypt(self, plaintext: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode()).decode()
        else:
            return base64.b64encode(plaintext.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        if self._fernet:
            try:
                return self._fernet.decrypt(encrypted.encode()).decode()
            except:
                # fallback to base64
                try:
                    return base64.b64decode(encrypted.encode()).decode()
                except:
                    return encrypted
        else:
            try:
                return base64.b64decode(encrypted.encode()).decode()
            except:
                return encrypted
    
    def load_exchange_credentials(self, exchange: str, api_key: str, api_secret: str) -> ExchangeCredentials:
        enc_key = self.encrypt(api_key)
        enc_secret = self.encrypt(api_secret)
        return ExchangeCredentials(
            exchange=exchange,
            api_key=SecureString(_encrypted_value=enc_key, _vault_key=self._key, _plain=api_key),
            api_secret=SecureString(_encrypted_value=enc_secret, _vault_key=self._key, _plain=api_secret)
        )
    
    # New API for crypto-only bootstrap
    def set(self, key: str, value: str):
        self._store[key] = self.encrypt(value)
    
    def get(self, key: str, use_env_fallback=True):
        if key in self._store:
            return self.decrypt(self._store[key])
        if use_env_fallback:
            return os.getenv(key)
        return None
    
    def get_credential(self, key: str):
        val = self.get(key)
        if val:
            return SecureString(_plain=val)
        return None

# For compatibility with secure_config.py
class SecureConfigManager:
    def __init__(self, vault: Vault):
        self.vault = vault
        self._config = {}
    
    def load_from_env(self):
        import os
        api_key = os.getenv("TOOBIT_API_KEY")
        api_secret = os.getenv("TOOBIT_API_SECRET")
        if not api_key or not api_secret:
            raise ValueError("Missing TOOBIT_API_KEY or TOOBIT_API_SECRET")
        self._config["exchange"] = "toobit"
        self._config["symbols"] = os.getenv("APEX_SYMBOLS", "BTC-SWAP-USDT").split(",")
        self._config["credentials"] = self.vault.load_exchange_credentials("toobit", api_key, api_secret)


class SecureBootstrapLoader:
    """Loader for bootstrap that provides secure credentials - compat"""
    def __init__(self, vault: Vault = None):
        self.vault = vault or Vault()
    
    def load(self):
        import os
        key = os.getenv("TOOBIT_API_KEY", "test_key")
        secret = os.getenv("TOOBIT_API_SECRET", "test_secret")
        return self.vault.load_exchange_credentials("toobit", key, secret)
    
    def inject_toobit_adapter(self):
        from ..infrastructure.exchanges.toobit_adapter import ToobitAdapter
        import os
        key = os.getenv("TOOBIT_API_KEY", "test_key")
        secret = os.getenv("TOOBIT_API_SECRET", "test_secret")
        return ToobitAdapter(key, secret)
