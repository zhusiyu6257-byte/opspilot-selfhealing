"""资产状态推导单测：区分"主机挂了"和"命令没跑成"。"""
from app.tasks.runbook import derive_asset_status


def test_success_marks_online():
    assert derive_asset_status(True, 0, "unreachable") == "online"


def test_connection_failure_marks_unreachable():
    assert derive_asset_status(False, -1, "online") == "unreachable"


def test_command_failure_keeps_current_status():
    # 主机能登录、只是命令返回非 0（如 rm 了不存在的文件），不该误判为宕机
    assert derive_asset_status(False, 1, "online") == "online"
    assert derive_asset_status(False, 127, "unknown") == "unknown"
