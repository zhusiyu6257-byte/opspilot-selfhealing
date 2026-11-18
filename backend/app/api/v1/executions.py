from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel

from app.db.session import get_db
from app.models.execution import TaskExecution

router = APIRouter(prefix="/executions", tags=["Executions"])


class ExecutionResponse(BaseModel):
    id: int
    task_id: str
    asset_id: Optional[int]
    task_type: str
    command: Optional[str]
    trigger_source: str
    status: str
    exit_code: Optional[int]
    stdout: Optional[str]
    stderr: Optional[str]
    duration_ms: Optional[float]
    created_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("", response_model=List[ExecutionResponse])
@router.get("/", response_model=List[ExecutionResponse], include_in_schema=False)
async def list_executions(
    asset_id: Optional[int] = Query(None, description="按资产 ID 筛选"),
    status: Optional[str] = Query(None, description="按状态筛选 (PENDING/RUNNING/SUCCESS/FAILED/REJECTED)"),
    limit: int = Query(20, ge=1, le=100, description="分页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """获取全平台任务与剧本执行历史审计记录"""
    stmt = select(TaskExecution).order_by(desc(TaskExecution.created_at))

    if asset_id:
        stmt = stmt.where(TaskExecution.asset_id == asset_id)
    if status:
        stmt = stmt.where(TaskExecution.status == status)

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
