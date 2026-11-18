"""指标接口单测：验证新增的磁盘/服务指标输出格式正确。"""
from app.api.v1.metrics import _disk_used_percent, _tcp_port_open, host_metrics


def test_disk_used_percent_is_in_range():
    value = _disk_used_percent("/")
    assert 0.0 <= value <= 100.0


def test_disk_used_percent_defaults_on_bad_path():
    assert _disk_used_percent("/definitely/not/a/path") == 0.0


def test_tcp_port_open_detects_listener():
    import socket

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        assert _tcp_port_open("127.0.0.1", port) == 1
        assert _tcp_port_open("127.0.0.1", 1) == 0
    finally:
        server.close()


def test_host_metrics_contains_all_series():
    import asyncio

    response = asyncio.run(host_metrics())
    body = response.body.decode()
    for name in (
        "opspilot_host_load1",
        "opspilot_host_uptime_seconds",
        "opspilot_host_disk_used_percent",
        "opspilot_host_service_up",
    ):
        assert name in body
    assert "text/plain" in response.media_type
