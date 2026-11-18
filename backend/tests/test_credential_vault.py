"""凭据加密单测：验证「密文可还原、篡改会被发现、没钥匙就拒绝」。"""
import pytest

from app.core.config import settings
from app.core.credential_vault import (
    CredentialVaultError,
    decrypt_secret,
    encrypt_secret,
)


def test_empty_password_returns_empty_envelope():
    assert encrypt_secret("") == ""
    assert decrypt_secret("") is None
    assert decrypt_secret(None) is None


def test_round_trip_preserves_secret():
    secret = "S3cr3t-P@ssw0rd!"
    envelope = encrypt_secret(secret)
    assert envelope != secret
    assert secret not in envelope
    assert decrypt_secret(envelope) == secret


def test_encryption_is_randomized():
    """Fernet 每次加密结果不同，防止相同密码产生相同密文暴露规律。"""
    first = encrypt_secret("same-password")
    second = encrypt_secret("same-password")
    assert first != second
    assert decrypt_secret(first) == decrypt_secret(second) == "same-password"


def test_tampered_envelope_is_rejected():
    envelope = encrypt_secret("hello")
    replacement = "AAA" if not envelope.endswith("AAA") else "BBB"
    tampered = envelope[:-3] + replacement
    with pytest.raises(CredentialVaultError):
        decrypt_secret(tampered)


def test_missing_key_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "SSH_CREDENTIAL_KEY", "")
    with pytest.raises(CredentialVaultError):
        encrypt_secret("pw")
    with pytest.raises(CredentialVaultError):
        decrypt_secret("any-envelope")


def test_invalid_key_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "SSH_CREDENTIAL_KEY", "not-a-fernet-key")
    with pytest.raises(CredentialVaultError):
        encrypt_secret("pw")
