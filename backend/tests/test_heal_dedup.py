"""冷却去重单测：验证指纹稳定、抢名额互斥、Redis 坏了降级为不去重。

这里不连真实 Redis，用假对象把「SET NX」的语义钉死。
"""
import pytest

from app.core import heal_dedup
from app.core.config import settings


def test_fingerprint_is_stable_and_order_insensitive():
    first = heal_dedup.fingerprint({"b": 2, "a": 1})
    second = heal_dedup.fingerprint({"a": 1, "b": 2})
    assert first == second
    assert first.startswith(heal_dedup.KEY_PREFIX)


def test_different_identity_produces_different_key():
    assert heal_dedup.fingerprint({"case": "a"}) != heal_dedup.fingerprint({"case": "b"})


@pytest.mark.asyncio
async def test_cooldown_zero_always_claims(monkeypatch):
    monkeypatch.setattr(settings, "ALERT_HEAL_COOLDOWN_SECONDS", 0)
    claimed, key = await heal_dedup.try_claim({"case": "a"})
    assert claimed is True
    assert key.startswith(heal_dedup.KEY_PREFIX)


@pytest.mark.asyncio
async def test_claim_is_exclusive_and_release_restores(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def set(self, key, value, nx=False, ex=None):
            if nx and key in self.store:
                return False
            self.store[key] = value
            return True

        async def delete(self, key):
            self.store.pop(key, None)

    fake = FakeRedis()
    monkeypatch.setattr(heal_dedup, "_redis", lambda: fake)
    monkeypatch.setattr(settings, "ALERT_HEAL_COOLDOWN_SECONDS", 60)

    claimed, key = await heal_dedup.try_claim({"case": "a"})
    assert claimed is True
    claimed_again, _ = await heal_dedup.try_claim({"case": "a"})
    assert claimed_again is False

    await heal_dedup.release(key)
    claimed_after_release, _ = await heal_dedup.try_claim({"case": "a"})
    assert claimed_after_release is True


@pytest.mark.asyncio
async def test_redis_down_degrades_to_no_dedup(monkeypatch):
    class BrokenRedis:
        async def set(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(heal_dedup, "_redis", lambda: BrokenRedis())
    monkeypatch.setattr(settings, "ALERT_HEAL_COOLDOWN_SECONDS", 60)
    claimed, _ = await heal_dedup.try_claim({"case": "a"})
    assert claimed is True
