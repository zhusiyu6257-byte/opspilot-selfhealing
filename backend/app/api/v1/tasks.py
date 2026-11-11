from celery.result import AsyncResult
from fastapi import APIRouter, status

from app.core.celery_app import celery_app
from app.tasks.ops import ping_host
from app.schemas.task import PingTaskRequest, TaskStatusResponse, TaskTriggerResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "/ping", response_model=TaskTriggerResponse, status_code=status.HTTP_202_ACCEPTED
)
async def trigger_ping_task(payload: PingTaskRequest):
    """异步分发主机探活任务，秒级响应 task_id，不卡死主工作线程"""
    task = ping_host.delay(payload.ip_address)
    return {
        "task_id": task.id,
        "status": task.status,
        "message": f"Ping task dispatched for {payload.ip_address}",
    }


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """根据 task_id 查询 Celery 任务在 Redis 中的最新状态与执行结果"""
    task_result = AsyncResult(task_id, app=celery_app)

    result_data = None
    if task_result.ready():
        if task_result.successful():
            result_data = task_result.result
        else:
            result_data = str(task_result.result)

    return {
        "task_id": task_id,
        "status": task_result.state,
        "result": result_data,
    }
