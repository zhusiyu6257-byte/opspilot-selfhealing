from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "opspilot_worker",
    broker=f"{settings.REDIS_URL}",
    backend=f"{settings.REDIS_URL}",
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# 直接导入任务模块，完成任务注册
import app.tasks.ops
