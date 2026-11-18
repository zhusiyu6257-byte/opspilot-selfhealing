"""最关键契约：邮件通知失败绝不能把成功的自愈变成 FAILED。"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.tasks import runbook


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, execution, asset):
        self._execution = execution
        self._asset = asset

    def query(self, model):
        # 按模型类型返回对应对象
        name = model.__name__
        if name == "TaskExecution":
            return _FakeQuery(self._execution)
        return _FakeQuery(self._asset)

    def commit(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_email_failure_does_not_flip_success_to_failed():
    execution = SimpleNamespace(
        status="PENDING", exit_code=None, stdout=None, stderr=None,
        duration_ms=None, finished_at=None,
    )
    asset = SimpleNamespace(status="unknown")
    session = _FakeSession(execution, asset)

    with patch.object(runbook, "SessionLocal", return_value=session), \
         patch.object(runbook, "execute_remote_command", return_value={
             "exit_code": 0, "stdout": "ok", "stderr": "", "success": True,
         }), \
         patch.object(runbook, "send_heal_result_email", side_effect=OSError("smtp down")):

        task = runbook.execute_command_task
        result = task.run(
            asset_id=1, hostname="127.0.0.1", port=22, username="root",
            command="uptime", trigger_source="ALERT_WEBHOOK",
            alert_name="CpuUsageHigh",
        )

    # 自愈本身成功，不受邮件失败影响
    assert result["success"] is True
    assert execution.status == "SUCCESS"
    assert asset.status == "online"


def test_manual_command_does_not_send_email():
    """手动执行命令不触发邮件通知，避免调试时刷屏。"""
    execution = SimpleNamespace(
        status="PENDING", exit_code=None, stdout=None, stderr=None,
        duration_ms=None, finished_at=None,
    )
    asset = SimpleNamespace(status="unknown")
    session = _FakeSession(execution, asset)

    with patch.object(runbook, "SessionLocal", return_value=session), \
         patch.object(runbook, "execute_remote_command", return_value={
             "exit_code": 0, "stdout": "ok", "stderr": "", "success": True,
         }), \
         patch.object(runbook, "send_heal_result_email") as send_mail:

        task = runbook.execute_command_task
        task.run(
            asset_id=1, hostname="127.0.0.1", port=22, username="root",
            command="uptime", trigger_source="MANUAL",
        )

    send_mail.assert_not_called()
