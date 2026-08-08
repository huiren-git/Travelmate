from dataclasses import dataclass
from typing import Any

import pytest

from src.api.v1 import sessions as sessions_api
from src.core.exceptions import AppException


@dataclass
class FakeTask:
    """模拟 LangGraph 的任务快照。"""

    id: str
    name: str
    path: tuple[Any, ...] = ()
    error: Exception | None = None
    interrupts: tuple[Any, ...] = ()
    result: Any = None


@dataclass
class FakeSnapshot:
    """模拟 LangGraph 的 StateSnapshot。"""

    values: dict[str, Any]
    created_at: str | None = None
    tasks: tuple[FakeTask, ...] = ()
    metadata: dict[str, Any] | None = None


@dataclass
class FakeCheckpointTuple:
    """模拟 checkpointer.alist 返回的 checkpoint 条目。"""

    config: dict[str, Any]


class FakeCheckpointer:
    """为会话管理接口提供可枚举、可删除的 fake checkpointer。"""

    # 初始化 fake checkpointer 绑定的 graph 和删除记录。
    def __init__(self, graph: "FakeGraph") -> None:
        self.graph = graph
        self.deleted_threads: list[str] = []

    # 枚举所有 fake checkpoint 条目。
    async def alist(self, config: Any):
        for thread_id in self.graph.snapshots:
            yield FakeCheckpointTuple(config={"configurable": {"thread_id": thread_id}})

    # 删除指定 thread 的 fake checkpoint。
    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted_threads.append(thread_id)
        self.graph.snapshots.pop(thread_id, None)


class FakeGraph:
    """为会话管理接口测试提供 fake graph。"""

    # 初始化 fake graph 的快照集合和 checkpointer。
    def __init__(self) -> None:
        self.snapshots: dict[str, FakeSnapshot] = {}
        self.checkpointer = FakeCheckpointer(self)

    # 返回指定 thread 的 fake checkpoint 快照。
    async def aget_state(self, config: dict[str, Any]) -> FakeSnapshot:
        thread_id = config["configurable"]["thread_id"]
        return self.snapshots.get(thread_id, FakeSnapshot(values={}))

    # 更新指定 thread 的 fake checkpoint State。
    async def aupdate_state(
        self,
        config: dict[str, Any],
        values: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        thread_id = config["configurable"]["thread_id"]
        snapshot = self.snapshots[thread_id]
        snapshot.values.update(values)
        return config


# 每个测试结束后清理活动运行注册表。
@pytest.fixture(autouse=True)
def clear_active_runs():
    sessions_api._active_runs.clear()
    yield
    sessions_api._active_runs.clear()


# 替换 sessions API 使用的 graph 实例。
def _patch_graph(monkeypatch, graph: FakeGraph) -> None:
    async def fake_get_graph():
        return graph

    monkeypatch.setattr(sessions_api, "_get_graph", fake_get_graph)


# 验证会话列表按用户过滤并按更新时间游标分页。
@pytest.mark.asyncio
async def test_get_sessions_filters_owner_and_paginates(monkeypatch):
    graph = FakeGraph()
    graph.snapshots = {
        "thread-new": FakeSnapshot(
            values={
                "user_id": "user-1",
                "destination": "北京",
                "start_date": "2026-08-10",
                "duration": 3,
                "is_finished": True,
            },
            created_at="2026-08-03T10:00:00Z",
        ),
        "thread-old": FakeSnapshot(
            values={
                "user_id": "user-1",
                "destination": "成都",
                "start_date": "2026-08-01",
                "duration": 2,
                "is_finished": True,
            },
            created_at="2026-08-01T14:30:00Z",
        ),
        "thread-other-user": FakeSnapshot(
            values={
                "user_id": "user-2",
                "destination": "杭州",
                "start_date": "2026-08-15",
                "duration": 3,
                "is_finished": True,
            },
            created_at="2026-08-04T10:00:00Z",
        ),
        "thread-deleted": FakeSnapshot(
            values={
                "user_id": "user-1",
                "destination": "广州",
                "start_date": "2026-08-20",
                "duration": 2,
                "is_finished": True,
                "deleted_at": "2026-08-04T11:00:00Z",
            },
            created_at="2026-08-04T11:00:00Z",
        ),
    }
    _patch_graph(monkeypatch, graph)

    first_page = await sessions_api.get_sessions(limit=1, cursor=None, user_id="user-1")
    second_page = await sessions_api.get_sessions(
        limit=20,
        cursor=first_page.data.next_cursor,
        user_id="user-1",
    )

    assert first_page.code == 200
    assert first_page.data.sessions[0].thread_id == "thread-new"
    assert first_page.data.sessions[0].status == "confirmed"
    assert first_page.data.has_more is True
    assert first_page.data.next_cursor == "2026-08-03T10:00:00Z"
    assert [item.thread_id for item in second_page.data.sessions] == ["thread-old"]
    assert second_page.data.sessions[0].status == "completed"
    assert second_page.data.has_more is False


# 验证快照接口返回 task_list、blackboard、图结构和 metadata。
@pytest.mark.asyncio
async def test_get_session_snapshot_returns_checkpoint_view(monkeypatch):
    graph = FakeGraph()
    graph.snapshots["thread-snapshot"] = FakeSnapshot(
        values={
            "user_id": "user-1",
            "thread_id": "thread-snapshot",
            "destination": "北京",
            "duration": 3,
            "trace_logs": ["raw llm trace"],
            "total_llm_calls": 2,
            "total_tokens_consumed": 345,
        },
        created_at="2026-08-03T10:00:00Z",
        tasks=(
            FakeTask(
                id="task-1",
                name="validator",
                path=("validator",),
                result={"passed": True},
            ),
        ),
    )
    _patch_graph(monkeypatch, graph)

    body = await sessions_api.get_session_snapshot(
        "thread-snapshot",
        include_raw_traces=True,
        user_id="user-1",
    )

    assert body["session_id"] == "thread-snapshot"
    assert body["state"]["blackboard"]["destination"] == "北京"
    assert body["state"]["task_list"][0]["status"] == "done"
    assert body["graph_structure"]["nodes"] == [
        "pre_fetcher",
        "supervisor",
        "itinerary_agent",
        "budget_agent",
        "validator",
    ]
    assert body["metadata"]["total_llm_calls"] == 2
    assert body["metadata"]["trace_logs"] == ["raw llm trace"]


# 验证删除接口会校验归属并将指定 thread 标记为逻辑删除。
@pytest.mark.asyncio
async def test_delete_session_marks_checkpoint_deleted(monkeypatch):
    graph = FakeGraph()
    graph.snapshots["thread-delete"] = FakeSnapshot(
        values={"user_id": "user-1", "thread_id": "thread-delete"},
        created_at="2026-08-03T10:00:00Z",
    )
    _patch_graph(monkeypatch, graph)

    response = await sessions_api.delete_session("thread-delete", user_id="user-1")

    assert response.status_code == 204
    assert graph.snapshots["thread-delete"].values["deleted_at"].endswith("Z")


# 验证会话正在运行时删除接口返回 409 冲突。
@pytest.mark.asyncio
async def test_delete_session_rejects_active_run(monkeypatch):
    graph = FakeGraph()
    graph.snapshots["thread-running"] = FakeSnapshot(
        values={"user_id": "user-1", "thread_id": "thread-running"},
    )
    sessions_api._active_runs["thread-running"] = object()
    _patch_graph(monkeypatch, graph)

    with pytest.raises(AppException) as exc_info:
        await sessions_api.delete_session("thread-running", user_id="user-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.details["thread_id"] == "thread-running"


# 验证 limit 超过说明书最大值时返回 40002 业务错误。
def test_paginate_sessions_rejects_limit_over_50():
    with pytest.raises(AppException) as exc_info:
        sessions_api._paginate_sessions([], limit=51, cursor=None)

    assert exc_info.value.code == 40002
    assert exc_info.value.details == {"field": "limit", "error": "limit 不能超过 50"}
