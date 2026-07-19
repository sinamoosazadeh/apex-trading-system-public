"""Tests for Security Infrastructure - Phase 15."""
import pytest
import os
from apex.security.vault import Vault
from apex.security.secure_config import SecureConfigManager
from apex.security.contracts import SecureString, ExchangeCredentials

@pytest.fixture
def vault():
    return Vault(master_password="super_secret_master_key_123")

def test_vault_encryption_decryption(vault):
    plaintext = "my_api_key_12345"
    encrypted = vault.encrypt(plaintext)
    
    assert encrypted != plaintext.encode()
    assert isinstance(encrypted, bytes)
    
    decrypted = vault.decrypt(encrypted)
    assert decrypted == plaintext

def test_secure_string_hides_value(vault):
    secret = "my_secret_password"
    secure_str = SecureString(
        _encrypted_value=vault.encrypt(secret),
        _vault_key=vault._key
    )
    
    assert "my_secret_password" not in repr(secure_str)
    assert "my_secret_password" not in str(secure_str)
    assert str(secure_str) == "***"
    
    assert secure_str.decrypt() == secret

def test_exchange_credentials_security(vault):
    creds = vault.load_exchange_credentials("toobit", "key123", "secret456")
    
    assert creds.exchange == "toobit"
    assert "key123" not in repr(creds)
    assert "secret456" not in repr(creds)
    assert creds.api_key.decrypt() == "key123"
    assert creds.api_secret.decrypt() == "secret456"

def test_secure_config_manager(monkeypatch, vault):
    monkeypatch.setenv("TOOBIT_API_KEY", "test_key_123")
    monkeypatch.setenv("TOOBIT_API_SECRET", "test_secret_456")
    monkeypatch.setenv("APEX_SYMBOLS", "BTC-SWAP-USDT,ETH-SWAP-USDT")
    
    manager = SecureConfigManager(vault)
    manager.load_from_env()
    
    assert manager.get("exchange") == "toobit"
    assert manager.get("symbols") == ["BTC-SWAP-USDT", "ETH-SWAP-USDT"]
    
    creds = manager.get("credentials")
    assert isinstance(creds, ExchangeCredentials)
    assert "test_key_123" not in repr(creds)
    
    assert manager.secure_boot_check() == True

def test_secure_boot_fails_on_missing_credentials(monkeypatch, vault):
    monkeypatch.delenv("TOOBIT_API_KEY", raising=False)
    monkeypatch.delenv("TOOBIT_API_SECRET", raising=False)
    
    manager = SecureConfigManager(vault)
    
    with pytest.raises(ValueError):
        manager.load_from_env()
