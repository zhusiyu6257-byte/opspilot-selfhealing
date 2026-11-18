from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "opspilot_worker",
    broker=f"{settings.REDIS_URL}",
    backend=f"{settings.REDIS_URL}",
    include=[
        "app.tasks.ops",
        "app.tasks.runbook",
    ],
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
