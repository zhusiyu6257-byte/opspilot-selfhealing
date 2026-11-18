"""邮件通知单测：mock SMTP，不真发信。

重点验证三条契约：
  1. 配置不全静默跳过（"没配邮件"是合法状态）
  2. 邮件内容正确、输出过长会截断
  3. 发信异常向上抛，由 Worker 的 try/except 兜住（通知失败不影响自愈结果）
"""
from unittest.mock import MagicMock, patch

from app.core import notification
from app.core.config import settings


def test_build_email_contains_key_info():
    subject, body = notification.build_heal_email(
        alert_name="CpuUsageHigh",
        host="127.0.0.1",
        command="uptime",
        status="SUCCESS",
        stdout="up 10 days",
        stderr="",
        task_id="abc123",
    )
    assert "CpuUsageHigh" in subject
    assert "127.0.0.1" in subject
    assert "自愈成功" in subject
    assert "abc123" in body
    assert "up 10 days" in body
    assert "（无）" in body  # 空 stderr 显示占位


def test_build_email_clips_long_output():
    _, body = notification.build_heal_email(
        alert_name="A",
        host="h",
        command="c",
        status="FAILED",
        stdout="x" * 5000,
        stderr="y" * 5000,
        task_id="t",
    )
    assert "截断" in body
    assert len(body) < 6000  # 被截到 2000 字符上限附近


def test_is_configured_requires_all_fields(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_USER", "user@qq.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "code")
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_TO", "to@qq.com")
    assert notification.is_configured() is True

    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    assert notification.is_configured() is False


def test_send_skipped_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_ENABLED", False)
    with patch.object(notification.smtplib, "SMTP_SSL") as smtp_ssl:
        result = notification.send_heal_result_email(
            alert_name="A", host="h", command="c", status="SUCCESS",
            stdout="", stderr="", task_id="t",
        )
    assert result is False
    smtp_ssl.assert_not_called()


def test_send_uses_smtp_ssl_and_credentials(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 465)
    monkeypatch.setattr(settings, "SMTP_USER", "from@example.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "secret-code")
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_TO", "a@example.com, b@example.com")

    server = MagicMock()
    server.__enter__ = MagicMock(return_value=server)
    server.__exit__ = MagicMock(return_value=False)
    with patch.object(notification.smtplib, "SMTP_SSL", return_value=server) as smtp_ssl:
        result = notification.send_heal_result_email(
            alert_name="A", host="h", command="c", status="FAILED",
            stdout="out", stderr="err", task_id="t",
        )

    assert result is True
    smtp_ssl.assert_called_once_with("smtp.example.com", 465, timeout=10)
    server.login.assert_called_once_with("from@example.com", "secret-code")
    # 收件人解析正确（逗号分隔、去空格）
    args = server.sendmail.call_args.args
    assert args[0] == "from@example.com"
    assert args[1] == ["a@example.com", "b@example.com"]


def test_send_exception_propagates_for_worker_to_catch(monkeypatch):
    """发信失败要向上抛，让 Worker 的 try/except 决定如何降级。"""
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_USER", "u")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "p")
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_TO", "to")
    with patch.object(notification.smtplib, "SMTP_SSL", side_effect=OSError("smtp down")):
        try:
            notification.send_heal_result_email(
                alert_name="A", host="h", command="c", status="SUCCESS",
                stdout="", stderr="", task_id="t",
            )
        except OSError:
            pass  # 预期：异常向上抛
        else:
            raise AssertionError("发信异常应向上抛，由 Worker 兜底")
