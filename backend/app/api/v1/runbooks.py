import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.command_guard import UnsafeCommandError, assert_safe_command
from app.core.credential_vault import CredentialVaultError, encrypt_secret
from app.db.session import get_db
from app.models.asset import Asset
from app.models.execution import TaskExecution
from app.tasks.runbook import execute_command_task

router = APIRouter(prefix="/runbooks", tags=["Runbooks"])


class CommandExecRequest(BaseModel):
    asset_id: int = Field(..., description="目标资产 ID")
    command: str = Field(..., min_length=1, description="要执行的 Shell 指令")
    ssh_password: str | None = Field(None, description="SSH 密码（若无免密密钥）")
    trigger_source: str = Field("MANUAL", description="触发源: MANUAL 或 ALERT_WEBHOOK")


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
    # 安全护栏：在查库、派发 Celery、写 PENDING 审计记录之前尽早拒绝。
    # 如果放到 worker 里再判，task_id 和审计脏记录都已经产生了。
    try:
        assert_safe_command(payload.command)
    except UnsafeCommandError as exc:
        # 拒绝也是一条值得查询的事实：先写一条 REJECTED 审计再返回 400。
        # 这样安全排查时能在审计表里看到「谁、什么时候、想跑什么命令」，
        # 而不是只有服务端日志里一行转瞬即逝的输出。
        db.add(TaskExecution(
            task_id=uuid.uuid4().hex,
            task_type="COMMAND",
            command=payload.command,
            trigger_source=payload.trigger_source,
            status="REJECTED",
            stderr=f"[安全护栏] {exc}",
        ))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    result = await db.execute(select(Asset).where(Asset.id == payload.asset_id))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset ID {payload.asset_id} 不存在",
        )

    # 凭据准备：本次手填的密码先加密成「信封」；没填就复用主机已存的密文。
    # 关键：队列里只跑信封，明文密码绝不进 Redis；已存密码在 API 侧
    # 连解都不解，只有真正要连 SSH 的 Worker 才会打开它。
    try:
        envelope = (
            encrypt_secret(payload.ssh_password)
            if payload.ssh_password
            else (asset.ssh_password_encrypted or "")
        )
    except CredentialVaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 1. 先落审计再派发：任务号由我们自己生成，审计记录和队列里的活儿
    #    从出生起共用同一个号码。旧顺序是「先派发再写 PENDING」，worker
    #    抢跑时会查不到记录，那条执行就永久没有审计；现在记录一定先于
    #    活儿存在，顺序问题从根上消失。
    task_id = uuid.uuid4().hex
    execution_record = TaskExecution(
        task_id=task_id,
        asset_id=asset.id,
        task_type="COMMAND",
        command=payload.command,
        trigger_source=payload.trigger_source,
        status="PENDING",
    )
    db.add(execution_record)
    await db.commit()

    # 2. 派发时显式带上同一个任务号（apply_async 的 task_id 参数），
    #    worker 里 self.request.id 就是它，两边天然对得上。
    try:
        execute_command_task.apply_async(
            kwargs={
                "asset_id": asset.id,
                "hostname": asset.ip_address,
                "port": asset.ssh_port,
                "username": asset.ssh_user,
                "command": payload.command,
                "password_envelope": envelope,
                "trigger_source": payload.trigger_source,
            },
            task_id=task_id,
        )
    except Exception as exc:
        # 派发失败不删记录：审计是只追加的事实，「派发失败」本身也是事实，
        # 删掉它等于让一次真实发生过的故障消失。改判 FAILED 并写明原因。
        execution_record.status = "FAILED"
        execution_record.stderr = f"[派发失败] {exc}"
        execution_record.finished_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"任务派发失败：{exc}",
        ) from exc

    return {
        "task_id": task_id,
        "message": f"Command dispatched to {asset.name} ({asset.ip_address})",
    }
