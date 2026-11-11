import paramiko
from typing import Dict, Any


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
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
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
    except Exception as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SSH Connection/Execution Error: {str(e)}",
            "success": False,
        }
    finally:
        client.close()
