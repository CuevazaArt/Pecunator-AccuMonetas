"""Tests for vault key derivation, encryption, and audit logging."""

import pytest

from runtime.core.security_util import (
    derive_key_from_passphrase,
    get_fernet_key_from_passphrase,
    encrypt_data,
    decrypt_data,
    audit_log_vault_event,
)


class TestKeyDerivation:
    """Test PBKDF2 key derivation from passphrase."""

    def test_derive_key_generates_salt(self):
        """Deriving key should generate salt if not provided."""
        passphrase = "my_secure_passphrase"
        key1, salt1 = derive_key_from_passphrase(passphrase)

        # Both should be base64 strings
        assert isinstance(key1, str)
        assert isinstance(salt1, str)
        assert len(key1) > 0
        assert len(salt1) > 0

    def test_derive_key_consistent(self):
        """Deriving with same passphrase and salt should produce same key."""
        passphrase = "my_secure_passphrase"
        key1, salt1 = derive_key_from_passphrase(passphrase)

        # Re-derive with the same salt
        key2, salt2 = derive_key_from_passphrase(passphrase, salt1)

        assert key1 == key2
        assert salt1 == salt2

    def test_derive_key_different_passphrases(self):
        """Different passphrases should produce different keys."""
        passphrase1 = "passphrase_1"
        passphrase2 = "passphrase_2"

        key1, salt1 = derive_key_from_passphrase(passphrase1)
        key2, salt2 = derive_key_from_passphrase(passphrase2, salt1)  # Use same salt

        assert key1 != key2

    def test_derive_key_different_salts(self):
        """Same passphrase with different salts should produce different keys."""
        passphrase = "same_passphrase"
        key1, salt1 = derive_key_from_passphrase(passphrase)
        key2, salt2 = derive_key_from_passphrase(passphrase)

        # Different salts should produce different keys
        assert salt1 != salt2
        assert key1 != key2


class TestFernetKeyDerivation:
    """Test conversion to Fernet-compatible key."""

    def test_fernet_key_from_passphrase(self):
        """Should produce valid Fernet key from passphrase."""
        passphrase = "test_passphrase"
        _, salt = derive_key_from_passphrase(passphrase)

        fernet_key = get_fernet_key_from_passphrase(passphrase, salt)
        assert isinstance(fernet_key, str)
        assert len(fernet_key) > 0

    def test_fernet_key_consistent(self):
        """Fernet key should be consistent with same passphrase and salt."""
        passphrase = "test_passphrase"
        _, salt = derive_key_from_passphrase(passphrase)

        fernet_key1 = get_fernet_key_from_passphrase(passphrase, salt)
        fernet_key2 = get_fernet_key_from_passphrase(passphrase, salt)

        assert fernet_key1 == fernet_key2


class TestEncryption:
    """Test encryption and decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypting and decrypting should return original data."""
        passphrase = "test_passphrase"
        plaintext = "secret_api_key_12345"

        # Derive key
        _, salt = derive_key_from_passphrase(passphrase)
        fernet_key = get_fernet_key_from_passphrase(passphrase, salt)

        # Encrypt
        ciphertext = encrypt_data(plaintext, fernet_key)
        assert ciphertext != plaintext

        # Decrypt
        recovered = decrypt_data(ciphertext, fernet_key)
        assert recovered == plaintext

    def test_decrypt_wrong_passphrase(self):
        """Decrypting with wrong passphrase should fail."""
        passphrase1 = "correct_passphrase"
        passphrase2 = "wrong_passphrase"
        plaintext = "secret_data"

        # Encrypt with passphrase1
        _, salt = derive_key_from_passphrase(passphrase1)
        fernet_key1 = get_fernet_key_from_passphrase(passphrase1, salt)
        ciphertext = encrypt_data(plaintext, fernet_key1)

        # Try to decrypt with passphrase2
        fernet_key2 = get_fernet_key_from_passphrase(passphrase2, salt)
        with pytest.raises(ValueError, match="Decryption failed"):
            decrypt_data(ciphertext, fernet_key2)

    def test_encrypt_empty_string(self):
        """Should handle empty plaintext."""
        passphrase = "test_passphrase"
        plaintext = ""

        _, salt = derive_key_from_passphrase(passphrase)
        fernet_key = get_fernet_key_from_passphrase(passphrase, salt)

        ciphertext = encrypt_data(plaintext, fernet_key)
        recovered = decrypt_data(ciphertext, fernet_key)

        assert recovered == plaintext

    def test_encrypt_unicode(self):
        """Should handle Unicode plaintext."""
        passphrase = "test_passphrase"
        plaintext = "секретные данные 🔐"

        _, salt = derive_key_from_passphrase(passphrase)
        fernet_key = get_fernet_key_from_passphrase(passphrase, salt)

        ciphertext = encrypt_data(plaintext, fernet_key)
        recovered = decrypt_data(ciphertext, fernet_key)

        assert recovered == plaintext


class TestAuditLogging:
    """Test vault event audit logging."""

    def test_audit_log_creates_file(self, tmp_path, monkeypatch):
        """Audit logging should create file if not exists."""
        # Mock data_dir to use temp directory
        def mock_data_dir():
            return str(tmp_path)

        import runtime.core.settings
        monkeypatch.setattr(runtime.core.settings, "data_dir", mock_data_dir)

        audit_log_vault_event("test_event", "test details")

        audit_path = tmp_path / "vault_audit.log"
        assert audit_path.exists()

    def test_audit_log_appends(self, tmp_path, monkeypatch):
        """Audit logging should append to existing file."""
        def mock_data_dir():
            return str(tmp_path)

        import runtime.core.settings
        monkeypatch.setattr(runtime.core.settings, "data_dir", mock_data_dir)

        audit_log_vault_event("event_1", "details_1")
        audit_log_vault_event("event_2", "details_2")

        audit_path = tmp_path / "vault_audit.log"
        content = audit_path.read_text()

        assert "event_1" in content
        assert "event_2" in content
        assert content.count("\n") >= 2

    def test_audit_log_sanitizes_details(self, tmp_path, monkeypatch):
        """Audit logging should sanitize sensitive data in details."""
        def mock_data_dir():
            return str(tmp_path)

        import runtime.core.settings
        monkeypatch.setattr(runtime.core.settings, "data_dir", mock_data_dir)

        # Log with API key in details
        audit_log_vault_event("unlock", "api_key=super_secret_key_12345")

        audit_path = tmp_path / "vault_audit.log"
        content = audit_path.read_text()

        # Should be sanitized
        assert "super_secret_key_12345" not in content
        assert "<redacted>" in content


class TestIntegration:
    """Integration tests for complete vault workflow."""

    def test_vault_lock_unlock_cycle(self):
        """Complete passphrase-based vault lock/unlock cycle."""
        passphrase = "my_vault_passphrase"

        # 1. Derive key and salt (first time setup)
        key1, salt = derive_key_from_passphrase(passphrase)
        fernet_key1 = get_fernet_key_from_passphrase(passphrase, salt)

        # 2. Store sensitive data (encrypted)
        secret_data = "binance_api_key_abc123"
        encrypted = encrypt_data(secret_data, fernet_key1)

        # 3. Later, unlock with same passphrase
        fernet_key2 = get_fernet_key_from_passphrase(passphrase, salt)
        decrypted = decrypt_data(encrypted, fernet_key2)

        # Should match
        assert decrypted == secret_data

    def test_key_rotation(self):
        """Rotating to new passphrase should work."""
        old_passphrase = "old_vault_passphrase"
        new_passphrase = "new_vault_passphrase"
        secret_data = "sensitive_api_key"

        # 1. Original setup
        _, old_salt = derive_key_from_passphrase(old_passphrase)
        old_fernet_key = get_fernet_key_from_passphrase(old_passphrase, old_salt)
        encrypted = encrypt_data(secret_data, old_fernet_key)

        # 2. Rotation: decrypt with old, re-encrypt with new
        decrypted = decrypt_data(encrypted, old_fernet_key)
        _, new_salt = derive_key_from_passphrase(new_passphrase)
        new_fernet_key = get_fernet_key_from_passphrase(new_passphrase, new_salt)
        re_encrypted = encrypt_data(decrypted, new_fernet_key)

        # 3. Verify new passphrase can unlock
        recovered = decrypt_data(re_encrypted, new_fernet_key)
        assert recovered == secret_data

        # 4. Verify old passphrase can't unlock new ciphertext
        with pytest.raises(ValueError):
            decrypt_data(re_encrypted, old_fernet_key)
