from pathlib import Path

from fastapi import APIRouter, Response

router = APIRouter(prefix="/metrics", tags=["Metrics"])


def _read_first_field(path: str, default: float = 0.0) -> float:
    """读取 /proc 下以空格分隔的指标文件第一个字段，读不到就回退 0。"""
    try:
        return float(Path(path).read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return default


@router.get("/host")
async def host_metrics() -> Response:
    """给 Prometheus 抓取的极简主机指标。

    这里不引入 node_exporter：直接读 Linux 暴露的 /proc 文件。
    生产环境建议换成 node_exporter，指标更完整、权限边界更清楚。
    """
    load1 = _read_first_field("/proc/loadavg")
    uptime_seconds = _read_first_field("/proc/uptime")

    body = "\n".join(
        [
            "# HELP opspilot_host_load1 宿主机 1 分钟平均负载",
            "# TYPE opspilot_host_load1 gauge",
            f"opspilot_host_load1 {load1}",
            "# HELP opspilot_host_uptime_seconds 宿主机运行秒数",
            "# TYPE opspilot_host_uptime_seconds gauge",
            f"opspilot_host_uptime_seconds {uptime_seconds}",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")
