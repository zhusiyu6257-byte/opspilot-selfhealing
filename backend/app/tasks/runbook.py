import logging
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.credential_vault import CredentialVaultError, decrypt_secret
from app.core.notification import send_heal_result_email
from app.core.ssh_client import execute_remote_command
from app.models.asset import Asset
from app.models.execution import TaskExecution

logger = logging.getLogger(__name__)

# 兼容读取数据库连接串，并转为 psycopg2/同步驱动
raw_uri = str(
    getattr(settings, "ASYNC_DATABASE_URI", None)
    or getattr(settings, "DATABASE_URL", None)
    or getattr(settings, "SQLALCHEMY_DATABASE_URI", None)
)
sync_db_uri = raw_uri.replace("+asyncpg", "")

engine = create_engine(sync_db_uri, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def derive_asset_status(success: bool, exit_code: int | None, current: str) -> str:
    """根据一次执行结果推导资产新状态（纯函数，便于测试）。

    - 成功            -> online
    - exit_code == -1 -> unreachable（连接层就没连上）
    - 其他失败        -> 保持原状态（主机通，只是命令没跑成）
    """
    if success:
        return "online"
    if exit_code == -1:
        return "unreachable"
    return current


@celery_app.task(name="tasks.execute_command", bind=True)
def execute_command_task(
    self,
    asset_id: int,
    hostname: str,
    port: int,
    username: str,
    command: str,
    password_envelope: str | None = None,
    trigger_source: str = "MANUAL",
    password: str | None = None,
    alert_name: str = "ManualCommand",
) -> dict:
    """异步执行远程 Shell 指令，并将生命周期与输出结果写入 task_executions 审计表"""
    task_id = self.request.id
    start_time = time.time()

    # 1. 尝试更新状态为 RUNNING
    with SessionLocal() as db:
        execution = db.query(TaskExecution).filter(TaskExecution.task_id == task_id).first()
        if execution:
            execution.status = "RUNNING"
            db.commit()

    # 2. 只在真正连接前打开信封；打不开就写成 FAILED，而不是拿错密码去撞 SSH。
    #    password 仅用于兼容改造前遗留的队列消息，新链路不会再传它。
    try:
        ssh_password = password if password is not None else (
            decrypt_secret(password_envelope) if password_envelope else None
        )
    except CredentialVaultError as exc:
        result = {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SSH Connection/Execution Error: {exc}",
            "success": False,
        }
    else:
        result = execute_remote_command(
            hostname=hostname,
            port=port,
            username=username,
            command=command,
            password=ssh_password,
        )
    duration_ms = round((time.time() - start_time) * 1000, 2)

    # 3. 回写最终执行审计结果 + 资产状态
    # 大白话：医生看完病，除了写病历（审计），还要更新病人档案上的"当前状态"。
    # 区分三种情况：
    #   - 命令执行成功           -> online（主机活着且能登录）
    #   - 连不上（exit_code=-1） -> unreachable（主机可能宕机/网络断了/密码错）
    #   - 命令本身失败（非0）    -> 不改状态（主机能登录，只是这条命令没跑成，
    #                              比如磁盘清理剧本里 rm 了不存在的文件）
    # 不把"命令失败"当成"主机挂了"，避免误判导致资产状态乱跳。
    final_status = "SUCCESS" if result.get("success") else "FAILED"
    with SessionLocal() as db:
        execution = db.query(TaskExecution).filter(TaskExecution.task_id == task_id).first()
        if execution:
            execution.status = final_status
            execution.exit_code = result.get("exit_code")
            execution.stdout = result.get("stdout")
            execution.stderr = result.get("stderr")
            execution.duration_ms = duration_ms
            execution.finished_at = datetime.utcnow()

        if asset_id:
            asset = db.query(Asset).filter(Asset.id == asset_id).first()
            if asset:
                asset.status = derive_asset_status(
                    bool(result.get("success")), result.get("exit_code"), asset.status
                )
        db.commit()

    # 4. 发结果通知（可选，附加服务）。
    # 只给告警自愈发，手动执行命令不发，避免人工调试时邮箱被刷屏。
    # 重中之重：整个发信过程用 try/except 兜住——自愈已经成功落库，
    # 就算 SMTP 挂了/授权码错了，也绝不能让这个任务变成 FAILED。
    # "修好了但没通知到"是小的可用性问题；"报失败但其实修好了"是错误的事实。
    if trigger_source == "ALERT_WEBHOOK":
        try:
            send_heal_result_email(
                alert_name=alert_name,
                host=hostname,
                command=command,
                status=final_status,
                stdout=result.get("stdout") or "",
                stderr=result.get("stderr") or "",
                task_id=task_id,
            )
        except Exception as exc:
            logger.warning("自愈结果邮件发送失败（不影响自愈结果） | task=%s | err=%s", task_id, exc)

    return {
        **result,
        "duration_ms": duration_ms,
        "task_id": task_id,
    }
