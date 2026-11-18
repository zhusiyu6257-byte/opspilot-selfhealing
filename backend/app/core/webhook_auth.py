"""Alertmanager Webhook 鉴权
==================================================================
为什么需要这一层：
  /alerts/webhook 是全系统唯一「外部系统主动推」的入口。它没有浏览器
  会话、没有登录态，只要能连到端口，就能让平台派发自愈剧本。
  命令护栏（command_guard）压低的是「一次调用最多造成多大破坏」，
  鉴权解决的是「谁有资格调用」。两者是纵深防御的两层，不能互相替代。

为什么是 Bearer Token，而不是 HMAC 签名：
  Alertmanager 的 webhook_configs.http_config 原生支持静态凭证
  （authorization.credentials / credentials_file），但不会给 payload
  计算签名。要做 HMAC（消息完整性 + 防篡改），必须加一层中继自己签名，
  并带上时间戳与 nonce，否则「签名+原文」仍可被原样重放。
  所以这一层的准确定位是「调用方认证」，不是「消息签名」。

失败语义（4xx 与 5xx 分开是有意为之）：
  - 服务端未配置 Token -> 503，fail closed。运维看到 503 就知道该补配置，
    而不是误以为对方没带凭证。「忘记配置 = 对全网开放」是常见事故来源。
  - 调用方缺 Token / Token 错 -> 401，并带 WWW-Authenticate: Bearer，
    让 Alertmanager 侧和网关都能读到标准语义。

信任前提与剩余边界：
  - Token 是共享密钥，明文过 HTTP 会被嗅探；生产必须 TLS 或可信内网。
  - 静态 Token 可被重放：拿到它的人能重复触发同一条告警。防重放要靠
    timestamp + nonce + 幂等键（Redis），属于下一阶段。
  - 鉴权通过只代表「调用方知道密钥」；剧本来自代码里的固定映射，
    调用方不能自带命令，且每条剧本仍要过 command_guard。
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_BEARER = "bearer"
_WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}


def require_alert_token(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """作为 FastAPI 依赖挂在路由上，业务函数本身不感知鉴权。

    横切关注点抽成依赖的好处：两条 webhook 路由可以共用；单测可以直接
    调用函数而不用起 HTTP 服务；路由里不会混入凭证解析代码。
    """
    expected = settings.ALERT_WEBHOOK_TOKEN

    if not expected:
        # 显式逃生舱：只在 development 且显式打开时放行，并留下告警日志
        if settings.ALERT_WEBHOOK_ALLOW_INSECURE and settings.ENVIRONMENT == "development":
            logger.warning("alert webhook accepted WITHOUT token (dev insecure mode)")
            return
        logger.error("alert webhook disabled: ALERT_WEBHOOK_TOKEN is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="服务端未配置 ALERT_WEBHOOK_TOKEN，Webhook 已按 fail-closed 策略关闭",
        )

    scheme, _, token = (authorization or "").partition(" ")
    client_ip = request.client.host if request.client else "unknown"
    if scheme.lower() != _BEARER or not token.strip():
        logger.warning("alert webhook rejected | ip=%s | reason=missing_bearer", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Bearer Token",
            headers=_WWW_AUTHENTICATE,
        )

    # 常量时间比较：普通 == 会按字节短路，理论上能通过响应耗时逐字节猜密钥。
    # 用 bytes 而非 str，避免非 ASCII 字符触发 TypeError 变成 500。
    provided = token.strip().encode("utf-8")
    if not hmac.compare_digest(provided, expected.encode("utf-8")):
        logger.warning("alert webhook rejected | ip=%s | reason=token_mismatch", client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer Token 无效",
            headers=_WWW_AUTHENTICATE,
        )
