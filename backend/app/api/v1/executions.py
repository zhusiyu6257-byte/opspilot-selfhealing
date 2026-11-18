from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
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


class ExecutionStats(BaseModel):
    total: int
    today_count: int
    success_count: int
    failed_count: int
    rejected_count: int
    success_rate: float


@router.get("/stats", response_model=ExecutionStats)
async def execution_stats(db: AsyncSession = Depends(get_db)):
    """聚合统计：给前端指标卡用，避免前端拉全量列表自己算。"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    total = await db.scalar(select(func.count(TaskExecution.id))) or 0
    today_count = await db.scalar(
        select(func.count(TaskExecution.id)).where(TaskExecution.created_at >= today)
    ) or 0
    success_count = await db.scalar(
        select(func.count(TaskExecution.id)).where(TaskExecution.status == "SUCCESS")
    ) or 0
    failed_count = await db.scalar(
        select(func.count(TaskExecution.id)).where(TaskExecution.status == "FAILED")
    ) or 0
    rejected_count = await db.scalar(
        select(func.count(TaskExecution.id)).where(TaskExecution.status == "REJECTED")
    ) or 0

    # 成功率分母剔除 REJECTED：被护栏拦下的命令从未执行，不该算进"执行失败"。
    executed = success_count + failed_count
    success_rate = round(success_count / executed * 100, 1) if executed else 0.0

    return ExecutionStats(
        total=total,
        today_count=today_count,
        success_count=success_count,
        failed_count=failed_count,
        rejected_count=rejected_count,
        success_rate=success_rate,
    )


@router.get("/by-task/{task_id}", response_model=ExecutionResponse)
async def get_execution_by_task_id(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """按任务号取单条完整审计（含 stdout/stderr 全文），供详情抽屉刷新用。"""
    result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == task_id)
    )
    execution = result.scalars().first()
    if not execution:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    return execution
