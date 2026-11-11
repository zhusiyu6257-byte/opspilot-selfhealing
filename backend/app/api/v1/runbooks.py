from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.models.asset import Asset
from app.tasks.runbook import execute_command_task

router = APIRouter(prefix="/runbooks", tags=["Runbooks"])


class CommandExecRequest(BaseModel):
    asset_id: int = Field(..., description="目标资产 ID")
    command: str = Field(..., min_length=1, description="要执行的 Shell 指令")
    ssh_password: str | None = Field(None, description="SSH 密码（若无免密密钥）")


class CommandExecResponse(BaseModel):
    task_id: str
    message: str


@router.post(
    "/execute",
    response_model=CommandExecResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_command_on_asset(
    payload: CommandExecRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Asset).where(Asset.id == payload.asset_id))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset ID {payload.asset_id} 不存在",
        )

    task = execute_command_task.delay(
        hostname=asset.ip_address,
        port=asset.ssh_port,
        username=asset.ssh_user,
        command=payload.command,
        password=payload.ssh_password,
    )

    return {
        "task_id": task.id,
        "message": f"Command dispatched to {asset.name} ({asset.ip_address})",
    }
