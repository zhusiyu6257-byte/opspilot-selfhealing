"""Webhook 鉴权单测：重点验证 fail-closed 语义。

门禁坏了要关门（没配 Token 就拒绝），这点和「去重优化坏了假装不存在」
正好相反，是这个项目刻意保持一致的取舍。
"""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import settings
from app.core.webhook_auth import require_alert_token


def _request(client: str = "1.2.3.4") -> Request:
    return Request({"type": "http", "client": (client, 1234), "headers": []})


def test_valid_bearer_passes():
    require_alert_token(_request(), "Bearer unit-test-token")


def test_lowercase_scheme_passes():
    require_alert_token(_request(), "bearer unit-test-token")


def test_missing_header_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        require_alert_token(_request(), None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


def test_wrong_token_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        require_alert_token(_request(), "Bearer wrong-token")
    assert exc_info.value.status_code == 401


def test_no_token_configured_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_TOKEN", "")
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_ALLOW_INSECURE", False)
    with pytest.raises(HTTPException) as exc_info:
        require_alert_token(_request(), "Bearer anything")
    assert exc_info.value.status_code == 503


def test_dev_escape_hatch_allows_without_token(monkeypatch):
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_TOKEN", "")
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_ALLOW_INSECURE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    require_alert_token(_request(), None)


def test_escape_hatch_ignored_outside_development(monkeypatch):
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_TOKEN", "")
    monkeypatch.setattr(settings, "ALERT_WEBHOOK_ALLOW_INSECURE", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc_info:
        require_alert_token(_request(), None)
    assert exc_info.value.status_code == 503
