"""审计闭环单测：验证「先落审计再派发」「密文不进队列」「拒绝也留痕」。

用假 AsyncSession + 假 apply_async 固定编排顺序，不连真实数据库和 Celery。
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1.runbooks import execute_command_on_asset
from app.core.credential_vault import decrypt_secret
from app.db.session import get_db
from app.main import app


class _FakeScalars:
    def __init__(self, asset):
        self._asset = asset

    def first(self):
        return self._asset


class _FakeResult:
    def __init__(self, asset):
        self._asset = asset

    def scalars(self):
        return _FakeScalars(self._asset)


class _FakeAsset:
    id = 7
    name = "test-host"
    ip_address = "127.0.0.1"
    ssh_port = 22
    ssh_user = "root"
    ssh_password_encrypted = ""


class FakeDB:
    def __init__(self, asset=None):
        self.asset = asset
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, stmt):
        return _FakeResult(self.asset)


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(db: FakeDB):
    app.dependency_overrides[get_db] = lambda: db


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_unsafe_command_writes_rejected_audit_without_dispatch(client):
    db = FakeDB()
    _override_db(db)
    with patch("app.api.v1.runbooks.execute_command_task.apply_async") as dispatch:
        response = client.post(
            "/api/v1/runbooks/execute",
            json={"asset_id": 7, "command": "rm -rf /"},
        )
    assert response.status_code == 400
    dispatch.assert_not_called()
    assert len(db.added) == 1
    assert db.added[0].status == "REJECTED"
    assert "ROOT_DELETE" in db.added[0].stderr


def test_safe_command_dispatches_with_matching_task_id_and_encrypted_envelope(client):
    db = FakeDB(_FakeAsset())
    _override_db(db)
    with patch("app.api.v1.runbooks.execute_command_task.apply_async") as dispatch:
        response = client.post(
            "/api/v1/runbooks/execute",
            json={
                "asset_id": 7,
                "command": "uptime",
                "ssh_password": "plain-secret",
            },
        )
    assert response.status_code == 202
    task_id = response.json()["task_id"]

    assert len(db.added) == 1
    record = db.added[0]
    assert record.task_id == task_id
    assert record.status == "PENDING"

    kwargs = dispatch.call_args.kwargs
    assert kwargs["task_id"] == task_id
    envelope = kwargs["kwargs"]["password_envelope"]
    assert envelope != "plain-secret"
    assert "plain-secret" not in str(kwargs)
    assert decrypt_secret(envelope) == "plain-secret"


def test_dispatch_failure_marks_audit_failed_not_deleted(client):
    db = FakeDB(_FakeAsset())
    _override_db(db)
    with patch(
        "app.api.v1.runbooks.execute_command_task.apply_async",
        side_effect=RuntimeError("broker down"),
    ):
        response = client.post(
            "/api/v1/runbooks/execute",
            json={"asset_id": 7, "command": "uptime"},
        )
    assert response.status_code == 502
    assert len(db.added) == 1
    assert db.added[0].status == "FAILED"
    assert "broker down" in db.added[0].stderr
