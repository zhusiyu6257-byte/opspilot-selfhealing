"""SSH 凭据保管箱
==================================================================
大白话：一把钥匙 + 一个带防伪封条的保险盒。

- 用的是「对称加密」：同一把钥匙既能上锁也能开锁。这里必须用可逆加密，
  不能用哈希（哈希像把文件打成指纹，打完就还原不回原文，而密码还要拿去登录）。
- Fernet 的密文自带时间戳和防篡改校验：有人改了一个字节，开锁时就会报错，
  而不是悄悄返回一个错密码去撞 SSH。
- 钥匙只存在环境变量里，不进数据库、不进代码仓库。钥匙丢了，旧密文就
  永远打不开 —— 这是加密的代价，也是为什么要备份钥匙。

职责边界：这个模块只管「锁」和「开」。谁有资格读密码、密码能不能进队列，
由调用它的接口和 Worker 决定。
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class CredentialVaultError(RuntimeError):
    """钥匙没配、钥匙不合法、或密文打不开时抛出，绝不悄悄返回空值。"""


def _fernet() -> Fernet:
    key = settings.SSH_CREDENTIAL_KEY
    if not key:
        raise CredentialVaultError(
            "未配置 SSH_CREDENTIAL_KEY：拒绝以明文保存或传递凭据。"
            "生成方式见 .env.example，生产环境应由密钥管理服务注入"
        )
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except (ValueError, TypeError) as exc:
        raise CredentialVaultError(f"SSH_CREDENTIAL_KEY 不是合法的 Fernet 密钥：{exc}") from exc


def encrypt_secret(plain: str) -> str:
    """明文 → 密文。空密码返回空串，表示「沿用免密密钥」。"""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(envelope: str | None) -> str | None:
    """密文 → 明文。仅 Worker 在真正连接 SSH 前调用。"""
    if not envelope:
        return None
    try:
        return _fernet().decrypt(envelope.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise CredentialVaultError(
            "凭据解密失败：钥匙可能已轮换，或密文被改动。请重新录入该主机密码"
        ) from exc
