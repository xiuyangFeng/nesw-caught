"""Tests for app.core.crypto key management and decryption behavior."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

import app.core.crypto as crypto


@pytest.fixture(autouse=True)
def isolated_crypto(monkeypatch, tmp_path):
    """Isolate crypto module state: fresh key file location, no env key."""
    monkeypatch.delenv("NEWS_CAUGHT_SECRET_KEY", raising=False)
    key_file = tmp_path / ".secret_key"
    monkeypatch.setattr(crypto, "_key_file_path", lambda: str(key_file))
    crypto._fernet = None
    yield key_file
    crypto._fernet = None


def test_generates_key_file_when_missing(isolated_crypto):
    key_file = isolated_crypto
    assert not key_file.exists()

    encrypted = crypto.encrypt_key("my-api-key")

    assert key_file.exists()
    assert encrypted != "my-api-key"
    assert encrypted.startswith("gAAAA")
    assert crypto.decrypt_key(encrypted) == "my-api-key"


def test_existing_key_file_is_reused_across_reinit(isolated_crypto):
    key_file = isolated_crypto
    encrypted = crypto.encrypt_key("persistent-secret")
    original_key_bytes = key_file.read_bytes()

    # Simulate process restart
    crypto._fernet = None

    assert crypto.decrypt_key(encrypted) == "persistent-secret"
    assert key_file.read_bytes() == original_key_bytes


def test_corrupt_key_file_fails_fast_and_is_never_overwritten(isolated_crypto):
    key_file = isolated_crypto
    key_file.write_bytes(b"not-a-valid-fernet-key")

    with pytest.raises(crypto.SecretKeyError):
        crypto.encrypt_key("some-secret")

    # The broken file must be left intact: regenerating would permanently
    # destroy all previously encrypted credentials.
    assert key_file.read_bytes() == b"not-a-valid-fernet-key"


def test_env_key_takes_precedence_and_no_file_is_created(isolated_crypto, monkeypatch):
    key_file = isolated_crypto
    monkeypatch.setenv("NEWS_CAUGHT_SECRET_KEY", Fernet.generate_key().decode("utf-8"))

    encrypted = crypto.encrypt_key("env-secret")

    assert crypto.decrypt_key(encrypted) == "env-secret"
    assert not key_file.exists()


def test_decrypt_empty_returns_empty():
    assert crypto.decrypt_key("") == ""
    assert crypto.decrypt_key(None) == ""


def test_decrypt_legacy_plaintext_is_returned_as_is(isolated_crypto):
    key_file = isolated_crypto

    # Values stored before encryption was introduced are not Fernet tokens
    # (no gAAAA prefix) and must be returned unchanged.
    assert crypto.decrypt_key("legacy-plain-secret") == "legacy-plain-secret"
    # Legacy passthrough should not even need to initialize the key.
    assert not key_file.exists()


def test_decrypt_fernet_token_with_wrong_key_raises():
    foreign_token = Fernet(Fernet.generate_key()).encrypt(b"secret").decode("utf-8")

    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt_key(foreign_token)
