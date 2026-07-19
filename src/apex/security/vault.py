"""Credential Vault - AES Encryption for sensitive data."""
from __future__ import annotations

import os
import base64
from typing import Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .contracts import SecureString, ExchangeCredentials

class Vault:
    """Manages encryption and decryption of secrets (Book I, 13.7)."""

    def __init__(self, master_password: str, salt: bytes = b'apex_static_salt_v1') -> None:
        """
        Initialize vault with a master password.
        In production, password should be injected via secure memory or HSM.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode('utf-8')))
        self._fernet = Fernet(key)
        self._key = key
        self._storage: Dict[str, bytes] = {}

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a string."""
        return self._fernet.encrypt(plaintext.encode('utf-8'))

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt a string."""
        return self._fernet.decrypt(ciphertext).decode('utf-8')

    def store_secret(self, name: str, plaintext: str) -> None:
        """Encrypt and store a secret."""
        self._storage[name] = self.encrypt(plaintext)

    def get_secure_string(self, name: str) -> SecureString:
        """Retrieve a secret as a SecureString (encrypted in memory)."""
        if name not in self._storage:
            raise KeyError(f"Secret '{name}' not found in vault")
        return SecureString(
            _encrypted_value=self._storage[name],
            _vault_key=self._key
        )

    def load_exchange_credentials(self, exchange: str, api_key: str, api_secret: str) -> ExchangeCredentials:
        """Load and encrypt exchange credentials."""
        return ExchangeCredentials(
            exchange=exchange,
            api_key=SecureString(_encrypted_value=self.encrypt(api_key), _vault_key=self._key),
            api_secret=SecureString(_encrypted_value=self.encrypt(api_secret), _vault_key=self._key)
        )
