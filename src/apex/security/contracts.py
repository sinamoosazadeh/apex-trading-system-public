
"""Security Contracts - Fixed for crypto-only"""
from __future__ import annotations
from dataclasses import dataclass
import base64
import os

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except:
    HAS_CRYPTO = False

@dataclass
class SecureString:
    _encrypted_value: bytes = b""
    _vault_key: str = ""
    _plain: str = ""
    
    def __post_init__(self):
        if self._plain and not self._encrypted_value:
            self._encrypted_value = base64.b64encode(self._plain.encode())
        # Ensure _encrypted_value is bytes
        if isinstance(self._encrypted_value, str):
            self._encrypted_value = self._encrypted_value.encode()
    
    def decrypt(self) -> str:
        return self.get()
    
    def get(self) -> str:
        try:
            if isinstance(self._encrypted_value, bytes):
                # Try fernet first
                if HAS_CRYPTO and b'gAAAA' in self._encrypted_value:
                    try:
                        pwd = os.getenv('APEX_MASTER', 'super_secret_master_key_123')
                        # Use _vault_key if available
                        key_material = self._vault_key
                        if key_material:
                            try:
                                # _vault_key is base64 encoded 32 bytes
                                raw = base64.b64decode(key_material.encode())
                                fernet_key = base64.urlsafe_b64encode(raw)
                                f = Fernet(fernet_key)
                                return f.decrypt(self._encrypted_value).decode()
                            except:
                                pass
                        # fallback
                        fernet_key = base64.urlsafe_b64encode(pwd.encode()[:32].ljust(32, b'0'))
                        f = Fernet(fernet_key)
                        return f.decrypt(self._encrypted_value).decode()
                    except:
                        pass
                return base64.b64decode(self._encrypted_value).decode()
            else:
                return self._plain
        except:
            return self._plain
    
    def __str__(self):
        return "***"
    def __repr__(self):
        return "SecureString(***REDACTED***)"

@dataclass
class ExchangeCredentials:
    exchange: str
    api_key: SecureString
    api_secret: SecureString
    
    def __repr__(self):
        return f"ExchangeCredentials(exchange='{self.exchange}', api_key=***, api_secret=***)"
