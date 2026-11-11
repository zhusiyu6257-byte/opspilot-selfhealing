from app.core.celery_app import celery_app
from app.core.ssh_client import execute_remote_command


@celery_app.task(name="tasks.execute_command")
def execute_command_task(
    hostname: str,
    port: int,
    username: str,
    command: str,
    password: str | None = None,
) -> dict:
    """异步执行远程 Shell 指令"""
    return execute_remote_command(
        hostname=hostname,
        port=port,
        username=username,
        command=command,
        password=password,
    )
