"""邮件通知 —— 用大白话说清楚这一层在做什么
==================================================================
自愈任务跑完后，除了写审计表（给自己看），还要"发封邮件告诉人"。
这里的邮件是**结果通知**：修好了没、跑了什么命令、输出是什么。

设计原则（很重要）：
  1. 通知是"附加服务"，不是主链路。发信失败绝不能让一次成功的自愈
     变成 FAILED —— 修好了就是修好了，没通知到人顶多少知道，不能颠倒因果。
     所以调用方必须用 try/except 包住本模块抛出的任何异常。
  2. 没配齐凭据就静默跳过。缺发件人/授权码/收件人任一，直接返回 False，
     不报错、不发信 —— 让"没配邮件"成为完全合法的运行状态。
  3. 授权码只从 settings（环境变量/.env）读，不进代码、不进数据库、不进日志。
     日志里只打收件人和主题，绝不打印密码或授权码。

用标准库 smtplib + email，不引入第三方依赖。QQ 邮箱用 SSL 465 端口。
"""

from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """配置是否齐全到可以发信。缺任一项就当作"没启用邮件"。"""
    return bool(
        settings.NOTIFICATION_EMAIL_ENABLED
        and settings.SMTP_USER
        and settings.SMTP_PASSWORD
        and settings.NOTIFICATION_EMAIL_TO
    )


def _recipients() -> list[str]:
    return [addr.strip() for addr in settings.NOTIFICATION_EMAIL_TO.split(",") if addr.strip()]


def build_heal_email(
    *,
    alert_name: str,
    host: str,
    command: str,
    status: str,
    stdout: str,
    stderr: str,
    task_id: str,
) -> tuple[str, str]:
    """构造邮件主题与正文（纯函数，不联网，便于测试）。

    正文只截取输出前若干字符：远程命令可能产生很长的输出，
    邮件是"快速看结果"，完整内容永远以审计表为准。
    """
    status_label = {
        "SUCCESS": "自愈成功",
        "FAILED": "自愈失败",
        "REJECTED": "被安全护栏拦截",
    }.get(status, status)

    subject = f"[OpsPilot] {status_label} · {alert_name} · {host}"

    def clip(text: str, limit: int = 2000) -> str:
        text = text or ""
        return text if len(text) <= limit else text[:limit] + "\n…（截断，完整输出见审计表）"

    body = "\n".join(
        [
            f"告警：{alert_name}",
            f"主机：{host}",
            f"状态：{status_label}",
            f"任务号：{task_id}",
            f"执行命令：{command}",
            "",
            "── 标准输出 ──",
            clip(stdout),
            "",
            "── 错误输出 ──",
            clip(stderr) or "（无）",
            "",
            "（本邮件由 OpsPilot 自愈平台自动发出）",
        ]
    )
    return subject, body


def send_heal_result_email(
    *,
    alert_name: str,
    host: str,
    command: str,
    status: str,
    stdout: str,
    stderr: str,
    task_id: str,
) -> bool:
    """发一封自愈结果邮件。配置不全返回 False；发送异常向上抛，由调用方兜底。

    成功返回 True。调用方应把本函数整体包在 try/except 里。
    """
    if not is_configured():
        logger.debug("邮件通知未配置齐全，跳过发送")
        return False

    subject, body = build_heal_email(
        alert_name=alert_name,
        host=host,
        command=command,
        status=status,
        stdout=stdout,
        stderr=stderr,
        task_id=task_id,
    )

    message = MIMEMultipart()
    message["From"] = formataddr((str(Header("OpsPilot", "utf-8")), settings.SMTP_USER))
    message["To"] = ", ".join(_recipients())
    message["Subject"] = Header(subject, "utf-8")
    message.attach(MIMEText(body, "plain", "utf-8"))

    # QQ 邮箱 SSL 465：用 SMTP_SSL 一把连上，不走STARTTLS升级，配置最简单。
    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, _recipients(), message.as_string())

    # 日志只记"发给谁、什么主题"，绝不打印授权码。
    logger.info("自愈结果邮件已发送 | to=%s | subject=%s", message["To"], subject)
    return True
