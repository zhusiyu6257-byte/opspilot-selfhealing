"""自愈「冷却去重」——先用大白话说清楚这个模块在干嘛
==================================================================
要解决的问题：
  Alertmanager 会一遍遍重复推同一条告警（它默认就是一直提醒你「还没好」），
  网络抖一下也会重发；别人偷看到一次合法请求，也能原样再发一遍。
  以前后端收到一次就真的远程执行一次，于是同一台机器被反复跑同一条剧本。

做法（像门口放一本登记簿）：
  1. 给每条告警算一张「脸」：把告警标签、开始时间、要跑的剧本揉成一串，
     压成一个短指纹（哈希）。同样的告警指纹一定一样，改一个字就不一样。
  2. 派活之前先去 Redis 登记「这张脸我来过了」。
     用 SET NX EX：只有「本子上还没有这张脸」时才写得进去，而且过一段时间
     自动擦掉（冷却时间）。「查」和「写」是一步完成的，所以两个请求同时
     进来，也只有一个能写上，不会都以为自己是第一次。
  3. 写不进去 = 冷却期内刚跑过 → 直接跳过，不再派发。

几个刻意的设计：
  - 登记放在「命令护栏」之后：被拦下的剧本不该占名额，否则你把剧本改对了，
    冷却期内还是跑不起来。
  - 派发失败要把登记擦掉（release）：不然一次网络抖动就让这条告警在
    冷却期内彻底没人管了。
  - 已经派发成功就不再擦掉：活儿已经交给 Worker 了，擦掉会导致重复远程执行。
    宁可这段时间少执行一次，也不要重复跑一遍命令。
  - Redis 挂了就「降级成不去重」，而不是拒绝服务：去重是省事的优化，不是门禁。
    这跟 webhook_auth 里「Token 没配好就一律拒绝」正好相反 ——
    门禁坏了要关上门，优化坏了应该假装它不存在。

和「盖章三件套」（HMAC + 时间戳 + 一次性编号）的区别：
  那个是给每封信盖防伪章、写发送时间、编流水号，用来防伪造和防原样重投，
  但 Alertmanager 自己不会盖章，得在中间加一个转发程序。
  这里不验证「信是谁写的、有没有被改」，只保证「同一件事别反复干」，
  不用加新服务，复用已经在跑的 Redis 就够了。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from redis import asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "opspilot:heal:"
_client: aioredis.Redis | None = None


def _redis() -> aioredis.Redis:
    """整个进程共用一个连接池，不必每条告警都重新连一次 Redis。"""
    global _client
    if _client is None:
        _client = aioredis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _client


def fingerprint(identity: dict[str, Any]) -> str:
    """把「这是哪一条告警」压成 Redis 键名。

    sort_keys 是必要的：字典顺序在不同版本/不同请求里可能不一样，
    顺序一变指纹就变，去重会悄悄失效。
    """
    raw = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return KEY_PREFIX + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


async def try_claim(identity: dict[str, Any]) -> tuple[bool, str]:
    """抢名额。返回 (抢到了吗, 键名)，键名留给出错时擦掉用。"""
    key = fingerprint(identity)
    ttl = settings.ALERT_HEAL_COOLDOWN_SECONDS
    if ttl <= 0:
        return True, key  # 0 = 关掉去重，方便对比演示

    try:
        acquired = await _redis().set(key, "1", nx=True, ex=ttl)
        return bool(acquired), key
    except Exception as exc:
        logger.warning("heal dedup unavailable, degrade to no-dedup | err=%s", exc)
        return True, key


async def release(key: str) -> None:
    """派发失败时把名额还回去，否则冷却期内这条告警再也不会被自愈。"""
    if settings.ALERT_HEAL_COOLDOWN_SECONDS <= 0:
        return
    try:
        await _redis().delete(key)
    except Exception as exc:
        logger.warning("heal dedup release failed | key=%s | err=%s", key, exc)
