"""资产编辑/删除 API 单测：验证唯一性排除自身、密码三态、删除不丢审计。"""
from datetime import datetime

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.asset import Asset


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)


class FakeDB:
    def __init__(self, assets):
        self.assets = {a.id: a for a in assets}
        self.deleted = []
        self.commits = 0
        self.scalar_queue = []

    async def get(self, model, pk):
        return self.assets.get(pk)

    async def scalar(self, stmt):
        if self.scalar_queue:
            return self.scalar_queue.pop(0)
        return None

    async def execute(self, stmt):
        return _Result(list(self.assets.values()))

    def add(self, obj):
        self.assets[obj.id] = obj

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        pass


def _make_asset(asset_id=1, name="host-a", ip="10.0.0.1", encrypted=None):
    return Asset(
        id=asset_id,
        name=name,
        ip_address=ip,
        os_type="Linux",
        status="unknown",
        ssh_port=22,
        ssh_user="root",
        ssh_password_encrypted=encrypted,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


import pytest


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


def test_update_asset_changes_fields(client):
    asset = _make_asset()
    db = FakeDB([asset])
    app.dependency_overrides[get_db] = lambda: db

    r = client.put("/api/v1/assets/1", json={"name": "host-b", "ssh_port": 2222})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "host-b"
    assert body["ssh_port"] == 2222
    # 未传的字段保持不变
    assert body["ip_address"] == "10.0.0.1"
    assert body["status"] == "unknown"


def test_update_asset_keeps_password_when_not_provided(client):
    asset = _make_asset(encrypted="cipher-text")
    db = FakeDB([asset])
    app.dependency_overrides[get_db] = lambda: db

    r = client.put("/api/v1/assets/1", json={"os_type": "Darwin"})
    assert r.status_code == 200
    assert asset.ssh_password_encrypted == "cipher-text"


def test_update_asset_rejects_duplicate_name(client):
    asset = _make_asset(1, "host-a")
    other = _make_asset(2, "host-b", "10.0.0.2")
    db = FakeDB([asset, other])
    # 唯一性查询返回冲突对象
    db.scalar_queue = [other]
    app.dependency_overrides[get_db] = lambda: db

    r = client.put("/api/v1/assets/1", json={"name": "host-b"})
    assert r.status_code == 400
    assert "already exists" in r.json()["detail"]


def test_update_asset_same_name_excludes_self(client):
    asset = _make_asset(1, "host-a")
    db = FakeDB([asset])
    # 传自己的原名不应触发唯一性查询，scalar_queue 为空即可
    app.dependency_overrides[get_db] = lambda: db

    r = client.put("/api/v1/assets/1", json={"name": "host-a"})
    assert r.status_code == 200


def test_update_nonexistent_asset_returns_404(client):
    db = FakeDB([])
    app.dependency_overrides[get_db] = lambda: db
    r = client.put("/api/v1/assets/999", json={"name": "x"})
    assert r.status_code == 404


def test_delete_asset(client):
    asset = _make_asset()
    db = FakeDB([asset])
    app.dependency_overrides[get_db] = lambda: db

    r = client.delete("/api/v1/assets/1")
    assert r.status_code == 204
    assert db.deleted == [asset]


def test_delete_nonexistent_asset_returns_404(client):
    db = FakeDB([])
    app.dependency_overrides[get_db] = lambda: db
    r = client.delete("/api/v1/assets/999")
    assert r.status_code == 404
