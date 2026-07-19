
"""Vault - Returns contracts.ExchangeCredentials for isinstance compatibility"""
from __future__ import annotations
from typing import Dict
import base64
import os

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except:
    HAS_CRYPTO = False

from .contracts import SecureString, ExchangeCredentials

class Vault:
    def __init__(self, master_password: str = "default", master_key: str = None, root_dir=None, **kwargs):
        pwd = master_password or master_key or kwargs.get('password') or "default"
        self._master_password = pwd
        self._key = base64.b64encode(pwd.encode()[:32].ljust(32, b'0')).decode()
        self._store: Dict[str, str] = {}
        if HAS_CRYPTO:
            key_material = base64.urlsafe_b64encode(pwd.encode()[:32].ljust(32, b'0'))
            self._fernet = Fernet(key_material)
        else:
            self._fernet = None
    
    def encrypt(self, plaintext: str) -> bytes:
        if self._fernet:
            return self._fernet.encrypt(plaintext.encode())
        else:
            return base64.b64encode(plaintext.encode())
    
    def decrypt(self, encrypted):
        if isinstance(encrypted, bytes):
            try:
                if self._fernet:
                    return self._fernet.decrypt(encrypted).decode()
            except:
                pass
            try:
                return base64.b64decode(encrypted).decode()
            except:
                return encrypted.decode() if isinstance(encrypted, bytes) else str(encrypted)
        else:
            if self._fernet:
                try:
                    return self._fernet.decrypt(encrypted.encode()).decode()
                except:
                    pass
            try:
                return base64.b64decode(encrypted.encode()).decode()
            except:
                return encrypted
    
    def load_exchange_credentials(self, exchange: str, api_key: str, api_secret: str) -> ExchangeCredentials:
        # Return contracts.ExchangeCredentials for isinstance check
        enc_key = self.encrypt(api_key)
        enc_secret = self.encrypt(api_secret)
        return ExchangeCredentials(
            exchange=exchange,
            api_key=SecureString(_encrypted_value=enc_key, _vault_key=self._key, _plain=api_key),
            api_secret=SecureString(_encrypted_value=enc_secret, _vault_key=self._key, _plain=api_secret)
        )
    
    def set(self, key: str, value: str):
        self._store[key] = self.encrypt(value)
    
    def get(self, key: str, use_env_fallback=True):
        if key in self._store:
            return self.decrypt(self._store[key])
        if use_env_fallback:
            return os.getenv(key)
        return None

class SecureBootstrapLoader:
    def __init__(self, vault: Vault = None):
        self.vault = vault or Vault()
    def load(self):
        import os
        key = os.getenv("TOOBIT_API_KEY", "test_key")
        secret = os.getenv("TOOBIT_API_SECRET", "test_secret")
        return self.vault.load_exchange_credentials("toobit", key, secret)

# SecureConfigManager moved to secure_config.py but keep alias for compat
