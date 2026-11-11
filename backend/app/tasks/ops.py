import time
from app.core.celery_app import celery_app


@celery_app.task(name="tasks.ping_host")
def ping_host(ip_address: str) -> dict:
    """模拟异步执行主机检测任务"""
    # 模拟网络探测网络耗时
    time.sleep(2)
    return {
        "target": ip_address,
        "reachable": True,
        "latency_ms": 12.5,
    }
