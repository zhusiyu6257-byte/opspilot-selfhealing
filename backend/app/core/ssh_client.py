import os
from typing import Dict, Any

import paramiko

from app.core.config import settings


def _configure_host_key_checking(client: paramiko.SSHClient) -> None:
    """决定「要不要核对对面这台机器的身份证」。

    AutoAddPolicy 会把第一次见到的主机指纹直接收下，等于仅凭对方自报
    家门就相信它；RejectPolicy 则要求指纹已经存在于可信清单中。
    """
    if not settings.SSH_STRICT_HOST_KEY_CHECKING:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return

    known_hosts = os.path.expanduser(settings.SSH_KNOWN_HOSTS_FILE)
    if not os.path.isfile(known_hosts):
        raise RuntimeError(
            f"SSH 主机指纹清单不存在：{known_hosts}。"
            "请先通过带外确认的主机指纹登记可信主机；"
            "仅限本地调试时才能显式设置 SSH_STRICT_HOST_KEY_CHECKING=false"
        )
    client.load_host_keys(known_hosts)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())


def execute_remote_command(
    hostname: str,
    port: int,
    username: str,
    command: str,
    password: str | None = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """通过 SSH 远程执行 Shell 命令"""
    client = paramiko.SSHClient()

    try:
        _configure_host_key_checking(client)
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            look_for_keys=True,
            allow_agent=True,
        )

        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out_msg = stdout.read().decode("utf-8", errors="replace")
        err_msg = stderr.read().decode("utf-8", errors="replace")

        return {
            "exit_code": exit_code,
            "stdout": out_msg,
            "stderr": err_msg,
            "success": exit_code == 0,
        }
    except paramiko.SSHException as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": (
                f"SSH 主机身份或连接校验失败：{e}。"
                "如果这是新主机，请先核对指纹并登记到 SSH_KNOWN_HOSTS_FILE"
            ),
            "success": False,
        }
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SSH Connection/Execution Error: {str(e)}",
            "success": False,
        }
    finally:
        client.close()
