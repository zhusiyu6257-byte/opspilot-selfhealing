"""命令安全护栏（Command Guard）
==================================================================
作用：在命令离开 HTTP 层、进入 Celery / Paramiko 之前，拦掉会造成
      不可逆破坏的 Shell 指令。

为什么放在这一层，而不是放进 ssh_client.py：
  1. 尽早拒绝。命令一旦 .delay() 进 Celery，就已经生成了 task_id、
     写了一条 PENDING 审计记录；这时再拒绝，就得回滚状态机，审计表里
     会留下「派发了但没执行」的脏记录。
  2. 两条入口共用。手动下发（/runbooks/execute）和告警自愈
     （/alerts/webhook）最终都走到 Paramiko，校验收敛在一处才不会漏。
  3. Paramiko 的 exec_command 只是把字符串原样交给远端 shell，
     它自己没有任何沙箱、权限或「危险」的概念 —— 边界只能在我们这侧。

重要：_normalize() 的结果只用于「判断」，绝不拿去执行。
  去引号、转小写、压空格会改变命令语义，只能喂给规则匹配器；
  真正下发的永远是调用方传进来的原始字符串。

边界（这不是沙箱）：
  归一化 + 黑名单能挡住手滑和常见绕过，挡不住所有变形。
  真正的隔离要靠受限 SSH 账号 / sudoers 白名单 / 只读根文件系统。
  这里解决的是：手滑、低水平攻击，以及 Webhook 暂未鉴权时
  「破坏面的上限」。

  另有一类规则不针对破坏，而针对「意图不完整」：rm 不带操作对象时
  GNU rm -f 会静默返回 exit 0，派发出去只会得到一条看似成功、
  实际什么都没做的审计记录。拒绝它比放行更诚实；但这类校验
  属于输入合法性检查，和「沙箱」仍是两件事。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_COMMAND_LENGTH = 2000

# 递归删除打到这里就是灾难；/tmp、/var/tmp 这类临时目录不在其中，
# 因为自愈剧本库里的 DiskUsageHigh 正是靠清理 /tmp 来回收空间。
SYSTEM_PATHS = frozenset(
    {
        "/", "/etc", "/usr", "/bin", "/sbin", "/boot", "/var", "/lib",
        "/lib64", "/home", "/root", "/dev", "/sys", "/proc", "/opt",
        "/srv", "/mnt", "/media",
    }
)

# sudo / env / command 只是包装层，真正要检查的是它后面的程序
_WRAPPERS = frozenset({"sudo", "env", "command", "nice", "nohup"})

_SEPARATORS = re.compile(r"&&|\|\||[;|&\n]")

# 2>/dev/null、>/tmp/x 这类是重定向，不是 rm 的删除目标
_REDIRECT_ONLY = re.compile(r"^\d*(?:&>|>>?|<<?|>&\d+)\S*$")


@dataclass(frozen=True)
class GuardDecision:
    """一次校验的结论。rule 是规则编号，方便日志检索和前端提示。"""

    allowed: bool
    rule: str = "OK"
    reason: str = ""
    segment: str = ""

    @property
    def message(self) -> str:
        if self.allowed:
            return "OK"
        return f"[安全护栏拦截] 规则 {self.rule}：{self.reason}（片段：{self.segment[:80]}）"


class UnsafeCommandError(ValueError):
    """命令未通过护栏。API 层捕获后转成 HTTP 400。"""

    def __init__(self, decision: GuardDecision):
        self.decision = decision
        super().__init__(decision.message)


def _normalize(command: str) -> str:
    """把命令变成「便于匹配」的形态，只用于检测。

    逐条对应一种真实绕过手法：
      反斜杠续行  -> rm\\\n-rf /      拆开关键字
      换行        -> 等价于分号，是命令边界
      $IFS        -> shell 的内部分隔符变量，可替代空格
      引号        -> r'm' -rf /       拆开程序名
      /bin/ 前缀  -> /bin/rm -rf /    绕过只看 rm 的规则
      大小写      -> RM -RF /
    """
    text = command.replace("\\\n", " ")
    text = text.replace("\n", " ; ")
    text = text.replace("\\/", "/")
    text = text.lower()
    text = re.sub(r"\$\{?ifs\}?", " ", text)
    text = re.sub(r"['\"`]", "", text)
    text = re.sub(r"/(?:usr/)?(?:bin|sbin)/", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _segments(normalized: str) -> list[str]:
    """按 shell 的命令分隔符切片段。

    `uptime && rm -rf /` 必须被当成两条命令检查，否则攻击者
    只要在危险命令前面拼一句无害命令就能混过去。
    """
    return [part.strip() for part in _SEPARATORS.split(normalized) if part.strip()]


def _check_rm(segment: str) -> GuardDecision | None:
    """rm 单独做「结构化解析」，而不是一条大正则。

    要区分这三条：
      rm -rf /tmp/mock_junk_*   -> 合法自愈动作，放行
      rm -rf /                  -> 不可逆破坏，拦截
      rm -rf                    -> 没有操作对象，命令不完整，拦截
    只看「含 rm -rf」会把第一条一起误杀，所以必须把 token 分成
    flag（-rf）和 operand（路径）两类，只判定 operand 的第一段。
    """
    tokens = segment.split()
    while tokens and tokens[0] in _WRAPPERS:
        tokens.pop(0)
    if not tokens or tokens[0].lstrip("(") != "rm":
        return None

    targets = [
        t for t in tokens[1:]
        if not t.startswith("-") and not _REDIRECT_ONLY.match(t)
    ]
    if not targets:
        return GuardDecision(
            False,
            "RM_MISSING_OPERAND",
            "rm 未指定删除目标；带 -f 时 shell 会静默返回 exit_code=0，"
            "派发后只会得到一条看似成功、实际什么都没做的审计记录",
            segment,
        )

    flags = "".join(t for t in tokens[1:] if t.startswith("-"))
    if "r" not in flags and "f" not in flags:
        return None

    for target in targets:
        bare = target.rstrip("/") or "/"
        if bare in ("", "/", "*", "/*"):
            return GuardDecision(False, "ROOT_DELETE", "禁止递归/强制删除根目录", segment)
        if bare.startswith("/"):
            first = "/" + bare.lstrip("/").split("/")[0]
            if first in SYSTEM_PATHS or first == "/*":
                return GuardDecision(
                    False, "SYSTEM_DELETE", f"禁止递归/强制删除系统路径 {first}", segment
                )
    return None


# 逐片段规则：每条对应一类不可逆破坏，理由会原样回给调用方
_SEGMENT_RULES: tuple[tuple[str, str, str], ...] = (
    ("FIND_ROOT_DELETE", r"\bfind\s+/[^;]*-delete\b", "删除文件不只有 rm，find -delete 同样不可逆"),
    ("DISK_DESTROY", r"\b(?:mkfs(?:\.\w+)?|wipefs|shred)\b", "禁止格式化或擦除块设备"),
    ("DD_TO_DEVICE", r"\bdd\b[^;]*\bof=/dev/", "禁止用 dd 直接覆写块设备"),
    ("DEVICE_REDIRECT", r">\s*/dev/(?:sd|nvme|hd|vd)", "禁止重定向输出覆盖块设备"),
    ("FORK_BOMB", r":\(\)\s*\{", "禁止 fork bomb（会耗尽主机进程表）"),
    ("HALT", r"\b(?:shutdown|poweroff|halt|reboot|init\s+0)\b", "禁止关机/重启，运维平台不应直接切断主机"),
)

# 整串规则：这些模式跨命令片段，切分后就看不见了
_GLOBAL_RULES: tuple[tuple[str, str, str], ...] = (
    ("CURL_PIPE_SH", r"(?:curl|wget)\b[^;|&]*\|\s*(?:ba|da|z|k)?sh\b", "禁止「下载即执行」，这是典型的供应链攻击入口"),
)


def check_command(command: str) -> GuardDecision:
    """纯函数：只判断、不抛异常，方便单测和以后做「预检」按钮。"""
    if not command or not command.strip():
        return GuardDecision(False, "EMPTY", "命令不能为空", str(command or ""))
    if len(command) > MAX_COMMAND_LENGTH:
        return GuardDecision(
            False, "TOO_LONG", f"命令长度超过 {MAX_COMMAND_LENGTH} 字符", command[:80]
        )

    normalized = _normalize(command)

    for rule, pattern, reason in _GLOBAL_RULES:
        if re.search(pattern, normalized):
            return GuardDecision(False, rule, reason, normalized[:120])

    for segment in _segments(normalized):
        decision = _check_rm(segment)
        if decision:
            return decision
        for rule, pattern, reason in _SEGMENT_RULES:
            if re.search(pattern, segment):
                return GuardDecision(False, rule, reason, segment)

    return GuardDecision(True, "OK", "", normalized)


def assert_safe_command(command: str) -> str:
    """API 层用这个：通过则返回原始命令，不通过抛 UnsafeCommandError。

    返回的是原始字符串，不是 normalized —— 这是刻意的设计。
    """
    decision = check_command(command)
    if not decision.allowed:
        logger.warning(
            "command rejected | rule=%s | segment=%s", decision.rule, decision.segment
        )
        raise UnsafeCommandError(decision)
    return command
