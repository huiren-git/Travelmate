"""Build and compile the TravelMate LangGraph workflow."""

import logging
from pathlib import Path
from typing import Any, Literal, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.config.settings import settings

try:
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
except ModuleNotFoundError:
    AsyncSqliteSaver = None

from src.agents.budget_agent import budget_agent_node
from src.agents.itinerary_agent import itinerary_agent_node
from src.agents.supervisor import supervisor_node
from src.graph.pre_fetcher import pre_fetcher_node
from src.graph.state import TravelAgentState
from src.graph.validator import validator_node

logger = logging.getLogger("travelmate.graph")

WORKER_NODES = {"itinerary_agent", "budget_agent"}
_async_checkpointer_context = None


# 根据 Supervisor 写入的 next_node 决定下一个工作节点。
def supervisor_router(state: TravelAgentState) -> Literal[
    "pre_fetcher",
    "__end__",
]:
    if state.get("is_finished", False):
        return "__end__"

    next_node = state.get("next_node") or "__end__"
    if next_node not in {*WORKER_NODES, "__end__"}:
        logger.warning("Unknown next_node=%s; ending workflow.", next_node)
        return "__end__"

    logger.info("supervisor_router -> pre_fetcher (worker=%s)", next_node)
    return "pre_fetcher"


# Supervisor 已完成自然语言参数提取后，预取数据，再进入其选定的工作节点。
def pre_fetcher_router(state: TravelAgentState) -> Literal[
    "itinerary_agent",
    "budget_agent",
    "__end__",
]:
    if state.get("is_finished", False):
        return "__end__"

    next_node = state.get("next_node") or "__end__"
    if next_node not in {*WORKER_NODES, "__end__"}:
        logger.warning("Unknown next_node=%s after pre-fetch; ending workflow.", next_node)
        return "__end__"
    logger.info("pre_fetcher_router -> %s", next_node)
    return next_node


# 根据 Validator 结果决定结束或重试当前工作分支。
def validator_router(state: TravelAgentState) -> Literal[
    "itinerary_agent",
    "budget_agent",
    "__end__",
]:
    if state.get("is_finished", False):
        return "__end__"

    attempts = state.get("validation_attempts", 0)
    # 预算自动微调闭环期间豁免 attempts 上限：循环由 budget_auto_retry<=2 与 is_finished 共同约束，不会死循环。
    if attempts >= 3 and not state.get("auto_reduce_budget"):
        logger.warning("Validation reached max attempts; ending workflow.")
        return "__end__"

    retry_node = state.get("next_node")
    if retry_node not in WORKER_NODES:
        retry_node = "itinerary_agent"

    logger.info("validator_router -> %s retry", retry_node)
    return retry_node


# 根据配置创建 LangGraph checkpointer。
def _build_checkpointer(checkpoint_path: Optional[str]):
    if checkpoint_path and checkpoint_path != ":memory:":
        logger.info("Async graph runtime requires AsyncSqliteSaver; using in-memory checkpointer here.")
    return MemorySaver()


# 异步创建应用运行时使用的 SQLite checkpointer。
async def _build_async_checkpointer(checkpoint_path: Optional[str]):
    global _async_checkpointer_context

    checkpoint_path = checkpoint_path or settings.database_path
    if not checkpoint_path or checkpoint_path == ":memory:" or AsyncSqliteSaver is None:
        if AsyncSqliteSaver is None:
            logger.info("langgraph-checkpoint-sqlite is not installed; using in-memory checkpointer.")
        return MemorySaver()

    try:
        Path(checkpoint_path).parent.mkdir(parents=True, exist_ok=True)
        context = AsyncSqliteSaver.from_conn_string(checkpoint_path)
        saver = await context.__aenter__()
        if hasattr(saver, "setup"):
            await saver.setup()
        _async_checkpointer_context = context
        return saver
    except Exception as exc:
        logger.warning("Async SQLite checkpointer unavailable (%s); using in-memory checkpointer.", exc)
        return MemorySaver()


# 关闭由 graph 模块持有的异步 SQLite checkpointer 上下文。
async def close_graph_checkpointers() -> None:
    global _async_checkpointer_context

    if _async_checkpointer_context is not None:
        try:
            await _async_checkpointer_context.__aexit__(None, None, None)
        except Exception as exc:
            logger.warning("SQLite checkpointer close failed: %s", exc)
        finally:
            _async_checkpointer_context = None


# 构建并编译 Supervisor -> worker -> Validator 工作流。
def build_graph(checkpoint_path: Optional[str] = None, checkpointer: Optional[Any] = None):
    builder = StateGraph(TravelAgentState)

    builder.add_node("pre_fetcher", pre_fetcher_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("itinerary_agent", itinerary_agent_node)
    builder.add_node("budget_agent", budget_agent_node)
    builder.add_node("validator", validator_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "pre_fetcher": "pre_fetcher",
            "__end__": END,
        },
    )
    builder.add_conditional_edges(
        "pre_fetcher",
        pre_fetcher_router,
        {
            "itinerary_agent": "itinerary_agent",
            "budget_agent": "budget_agent",
            "__end__": END,
        },
    )
    builder.add_edge("itinerary_agent", "validator")
    builder.add_edge("budget_agent", "validator")
    builder.add_conditional_edges(
        "validator",
        validator_router,
        {
            "itinerary_agent": "itinerary_agent",
            "budget_agent": "budget_agent",
            "__end__": END,
        },
    )

    return builder.compile(checkpointer=checkpointer or _build_checkpointer(checkpoint_path))


_graph_instance = None


# 返回 FastAPI 应用复用的单例图实例。
def get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance


# 异步返回 FastAPI 应用复用的单例图实例。
async def get_graph_async():
    global _graph_instance
    if _graph_instance is None:
        checkpointer = await _build_async_checkpointer(settings.database_path)
        _graph_instance = build_graph(checkpointer=checkpointer)
    return _graph_instance
