import os
import shutil
import socket
from pathlib import Path

from fastapi import APIRouter, Response

router = APIRouter(prefix="/metrics", tags=["Metrics"])


def _read_first_field(path: str, default: float = 0.0) -> float:
    """读取 /proc 下以空格分隔的指标文件第一个字段，读不到就回退 0。"""
    try:
        return float(Path(path).read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return default


def _disk_used_percent(path: str = "/") -> float:
    """磁盘使用率百分比。shutil 跨平台可读，读不到回退 0。"""
    try:
        usage = shutil.disk_usage(path)
        if not usage.total:
            return 0.0
        return round(usage.used / usage.total * 100, 2)
    except OSError:
        return 0.0


def _tcp_port_open(host: str, port: int, timeout: float = 0.5) -> int:
    """本机某端口是否可连：1=通, 0=不通。用于"服务是否存活"这类探活。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return 1
    except OSError:
        return 0


@router.get("/host")
async def host_metrics() -> Response:
    """给 Prometheus 抓取的主机指标。

    这里不引入 node_exporter：直接读 Linux /proc + shutil + socket。
    生产环境建议换成 node_exporter，指标更完整、权限边界更清楚。
    """
    load1 = _read_first_field("/proc/loadavg")
    uptime_seconds = _read_first_field("/proc/uptime")
    disk_used_percent = _disk_used_percent("/")
    # 用回环地址的 SSH 端口作为"服务存活"信号；端口可用环境变量 METRIC_SSH_PORT 改。
    try:
        ssh_port = int(os.environ.get("METRIC_SSH_PORT", "22"))
    except ValueError:
        ssh_port = 22
    service_up = _tcp_port_open("127.0.0.1", ssh_port)

    body = "\n".join(
        [
            "# HELP opspilot_host_load1 宿主机 1 分钟平均负载",
            "# TYPE opspilot_host_load1 gauge",
            f"opspilot_host_load1 {load1}",
            "# HELP opspilot_host_uptime_seconds 宿主机运行秒数",
            "# TYPE opspilot_host_uptime_seconds gauge",
            f"opspilot_host_uptime_seconds {uptime_seconds}",
            "# HELP opspilot_host_disk_used_percent 根分区使用率百分比",
            "# TYPE opspilot_host_disk_used_percent gauge",
            f"opspilot_host_disk_used_percent {disk_used_percent}",
            "# HELP opspilot_host_service_up SSH 服务端口是否可连（1=通 0=不通）",
            "# TYPE opspilot_host_service_up gauge",
            f"opspilot_host_service_up {service_up}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
