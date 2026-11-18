"""配置层安全校验单测：生产环境禁止"图省事"开关，启动即失败。"""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_kwargs(**overrides):
    kwargs = {
        "ENVIRONMENT": "production",
        "ALERT_WEBHOOK_TOKEN": "a-token",
        "SSH_CREDENTIAL_KEY": "a-key",
    }
    kwargs.update(overrides)
    return kwargs


def test_production_allows_secure_settings():
    settings = Settings(**_base_kwargs())
    assert settings.ENVIRONMENT == "production"
    assert settings.ALERT_WEBHOOK_ALLOW_INSECURE is False
    assert settings.SSH_STRICT_HOST_KEY_CHECKING is True


def test_production_rejects_insecure_webhook():
    with pytest.raises(ValidationError, match="ALERT_WEBHOOK_ALLOW_INSECURE"):
        Settings(**_base_kwargs(ALERT_WEBHOOK_ALLOW_INSECURE=True))


def test_production_rejects_disabled_host_key_checking():
    with pytest.raises(ValidationError, match="SSH_STRICT_HOST_KEY_CHECKING"):
        Settings(**_base_kwargs(SSH_STRICT_HOST_KEY_CHECKING=False))


def test_development_allows_insecure_flags_for_local_debug():
    settings = Settings(
        ENVIRONMENT="development",
        ALERT_WEBHOOK_ALLOW_INSECURE=True,
        SSH_STRICT_HOST_KEY_CHECKING=False,
    )
    assert settings.ALERT_WEBHOOK_ALLOW_INSECURE is True
    assert settings.SSH_STRICT_HOST_KEY_CHECKING is False


def test_unknown_environment_is_rejected():
    with pytest.raises(ValidationError):
        Settings(**_base_kwargs(ENVIRONMENT="prodution"))
