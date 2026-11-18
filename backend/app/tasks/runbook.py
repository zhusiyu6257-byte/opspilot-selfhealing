import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.credential_vault import CredentialVaultError, decrypt_secret
from app.core.ssh_client import execute_remote_command
from app.models.execution import TaskExecution

# 兼容读取数据库连接串，并转为 psycopg2/同步驱动
raw_uri = str(
    getattr(settings, "ASYNC_DATABASE_URI", None)
    or getattr(settings, "DATABASE_URL", None)
    or getattr(settings, "SQLALCHEMY_DATABASE_URI", None)
)
sync_db_uri = raw_uri.replace("+asyncpg", "")

engine = create_engine(sync_db_uri, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


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

    # 3. 回写最终执行审计结果
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
            db.commit()

    return {
        **result,
        "duration_ms": duration_ms,
        "task_id": task_id,
    }
