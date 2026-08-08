import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.api.v1 import chat as chat_api
from src.api.v1.chat import ChatStreamRequest, ResumeRequest, UserDecision
from src.core.exceptions import AppException


@dataclass
class FakeTask:
    """模拟 LangGraph 的中断任务。"""

    interrupts: tuple[Any, ...] = ()


@dataclass
class FakeSnapshot:
    """模拟 LangGraph 的 StateSnapshot。"""

    values: dict[str, Any]
    tasks: tuple[FakeTask, ...] = ()


class FakeGraph:
    """为 API 测试提供可控的异步 graph。"""

    # 初始化 fake graph 的 State、事件和调用记录。
    def __init__(self) -> None:
        self.snapshots: dict[str, FakeSnapshot] = {}
        self.stream_inputs: list[Any] = []
        self.started = asyncio.Event()
        self.block = False

    # 返回指定 thread 的 fake checkpoint。
    async def aget_state(self, config: dict[str, Any]) -> FakeSnapshot:
        thread_id = config["configurable"]["thread_id"]
        return self.snapshots.get(
            thread_id,
            FakeSnapshot(values={}),
        )

    # 生成模拟的 graph 节点更新和最终状态。
    async def astream(self, graph_input: Any, config: dict[str, Any], **_: Any):
        thread_id = config["configurable"]["thread_id"]
        self.stream_inputs.append(graph_input)
        self.started.set()
        if self.block:
            await asyncio.Event().wait()

        yield {"itinerary_agent": {"daily_itinerary": [{"day": 1}]}}
        self.snapshots[thread_id] = FakeSnapshot(
            values={
                "messages": [HumanMessage(content="已生成行程")],
                "user_id": "user-1",
                "thread_id": thread_id,
                "destination": "北京",
                "duration": 3,
                "daily_itinerary": [{"day": 1}],
                "budget": None,
                "is_finished": True,
            }
        )


# 每个测试结束后清理 API 进程内的活动任务注册表。
@pytest.fixture(autouse=True)
def clear_active_runs():
    chat_api._active_runs.clear()
    yield
    chat_api._active_runs.clear()


# 验证 stream 接口能够把 graph 更新编码成 SSE 事件。
@pytest.mark.asyncio
async def test_chat_stream_returns_sse_events(monkeypatch):
    graph = FakeGraph()
    # 返回 fake graph 以避免测试调用真实 LLM 和外部 API。
    async def fake_get_graph():
        return graph

    monkeypatch.setattr(chat_api, "_get_graph", fake_get_graph)

    response = await chat_api.chat_stream(
        ChatStreamRequest(
            thread_id="thread-stream",
            message="帮我设计一个北京3日游",
        ),
        user_id="user-1",
    )
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    assert response.media_type == "text/event-stream"
    assert "event: node" in body
    assert "event: done" in body
    assert graph.stream_inputs


# 验证 stop 接口能够取消正在执行的 graph 任务并返回部分结果信息。
@pytest.mark.asyncio
async def test_stop_chat_cancels_active_run(monkeypatch):
    graph = FakeGraph()
    graph.block = True
    # 返回 fake graph 以便测试停止正在阻塞的生成任务。
    async def fake_get_graph():
        return graph

    monkeypatch.setattr(chat_api, "_get_graph", fake_get_graph)

    response = await chat_api.chat_stream(
        ChatStreamRequest(
            thread_id="thread-stop",
            message="帮我设计一个北京3日游",
        ),
        user_id="user-1",
    )
    await asyncio.wait_for(graph.started.wait(), timeout=1)

    result = await chat_api.stop_chat("thread-stop", user_id="user-1")
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    assert result["code"] == 200
    assert result["data"]["thread_id"] == "thread-stop"
    assert "event: stopped" in body


# 验证 resume 接口只接受处于 LangGraph interrupt 状态的会话。
@pytest.mark.asyncio
async def test_resume_chat_uses_langgraph_command(monkeypatch):
    graph = FakeGraph()
    thread_id = "thread-resume"
    graph.snapshots[thread_id] = FakeSnapshot(
        values={
            "user_id": "user-1",
            "thread_id": thread_id,
            "is_finished": False,
        },
        tasks=(FakeTask(interrupts=("budget_confirmation",)),),
    )
    # 返回 fake graph 以便测试 resume 的 Command 输入。
    async def fake_get_graph():
        return graph

    monkeypatch.setattr(chat_api, "_get_graph", fake_get_graph)

    response = await chat_api.resume_chat(
        ResumeRequest(
            thread_id=thread_id,
            user_decision=UserDecision(
                action="modify",
                hint="把预算压缩到 2200 元以内",
                note="优先保留历史景点",
            ),
        ),
        user_id="user-1",
    )
    chunks = [chunk async for chunk in response.body_iterator]
    body = "".join(chunk.decode() if isinstance(chunk, bytes) else chunk for chunk in chunks)

    assert "event: done" in body
    assert isinstance(graph.stream_inputs[0], Command)
    assert graph.stream_inputs[0].resume["action"] == "modify"
    assert graph.stream_inputs[0].resume["hint"] == "把预算压缩到 2200 元以内"


# 验证修改决策缺少 hint 时返回说明书约定的业务错误。
def test_resume_chat_rejects_modify_without_hint():
    with pytest.raises(AppException) as exc_info:
        chat_api._validate_decision(UserDecision(action="modify"))

    assert exc_info.value.code == 40005
