"""审计统计/详情 API 单测：验证成功率口径（剔除 REJECTED）与 404。"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.execution import TaskExecution


class _Scalars:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)


class FakeDB:
    def __init__(self, counts=None, execution=None):
        # counts 顺序对应 stats 里的 5 次 scalar 调用：
        # total, today, success, failed, rejected
        self.counts = counts or [0, 0, 0, 0, 0]
        self.count_index = 0
        self.execution = execution

    async def scalar(self, stmt):
        value = self.counts[self.count_index]
        self.count_index += 1
        return value

    async def execute(self, stmt):
        return _Result([self.execution] if self.execution else [])


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


def test_stats_success_rate_excludes_rejected(client):
    # 成功 8、失败 2、被拦 100：成功率应是 80%，不是 8/110
    db = FakeDB(counts=[110, 5, 8, 2, 100])
    app.dependency_overrides[get_db] = lambda: db

    r = client.get("/api/v1/executions/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 110
    assert body["success_count"] == 8
    assert body["failed_count"] == 2
    assert body["rejected_count"] == 100
    assert body["success_rate"] == 80.0


def test_stats_zero_executions_returns_zero_rate(client):
    db = FakeDB(counts=[0, 0, 0, 0, 0])
    app.dependency_overrides[get_db] = lambda: db
    r = client.get("/api/v1/executions/stats")
    assert r.status_code == 200
    assert r.json()["success_rate"] == 0.0


def test_execution_detail_by_task_id(client):
    execution = TaskExecution(
        id=1,
        task_id="abc123",
        asset_id=7,
        task_type="AUTO_HEAL",
        command="uptime",
        trigger_source="ALERT_WEBHOOK",
        status="SUCCESS",
        stdout="full output here",
        created_at=datetime.utcnow(),
    )
    db = FakeDB(execution=execution)
    app.dependency_overrides[get_db] = lambda: db

    r = client.get("/api/v1/executions/by-task/abc123")
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == "abc123"
    assert body["stdout"] == "full output here"
    assert body["trigger_source"] == "ALERT_WEBHOOK"


def test_execution_detail_not_found(client):
    db = FakeDB(execution=None)
    app.dependency_overrides[get_db] = lambda: db
    r = client.get("/api/v1/executions/by-task/missing")
    assert r.status_code == 404
