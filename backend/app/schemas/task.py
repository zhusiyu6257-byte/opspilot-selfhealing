from typing import Any
from pydantic import BaseModel, Field


class PingTaskRequest(BaseModel):
    ip_address: str = Field(..., max_length=45, description="目标主机 IP")


class TaskTriggerResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Any | None = None
