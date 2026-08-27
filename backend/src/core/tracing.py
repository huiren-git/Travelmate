# src/core/tracing.py

import contextvars
import json
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Awaitable, Callable, Optional, Tuple

import inspect
import asyncio
from src.services.tracing_db import insert_span_start, update_span_end

from contextlib import asynccontextmanager


# ============================================================
# 1. ContextVar
# ============================================================

# 当前请求 / 对话的 Trace ID
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id",
    default=None,
)

# 当前请求的 Span 栈
#
# 使用 tuple 而不是 list：
# 1. 避免多个 Context 共享同一个可变对象
# 2. 更符合 ContextVar 的使用方式
# 3. 方便通过 token reset 恢复上下文
_span_stack_var: contextvars.ContextVar[Tuple[str, ...]] = contextvars.ContextVar(
    "span_stack",
    default=(),
)

# ============================================================
# 2. ID 生成
# ============================================================

def generate_trace_id() -> str:
    """
    生成 Trace ID。

    格式：
        trc_{YYYYMMDD}_{12位短码}

    示例：
        trc_20260815_a1b2c3d4e5f6
    """
    date_str = datetime.now().strftime("%Y%m%d")
    short_code = uuid.uuid4().hex[:12]

    return f"trc_{date_str}_{short_code}"


def generate_span_id() -> str:
    """
    生成 Span ID。

    格式：
        spn_{12位短码}

    示例：
        spn_x9y8z7w6v5u4
    """
    short_code = uuid.uuid4().hex[:12]

    return f"spn_{short_code}"


# ============================================================
# 3. Trace ID 操作
# ============================================================

def set_trace_id(trace_id: str) -> contextvars.Token:
    """
    设置当前 Context 的 Trace ID。

    返回 Token，调用方如果需要恢复之前的 Trace ID，
    可以使用：

        token = set_trace_id(trace_id)
        try:
            ...
        finally:
            reset_trace_id(token)
    """
    return _trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """
    获取当前协程的 Trace ID。
    """
    return _trace_id_var.get()


def reset_trace_id(token: contextvars.Token) -> None:
    """
    恢复之前的 Trace ID。
    """
    _trace_id_var.reset(token)


# ============================================================
# 4. Span 栈操作
# ============================================================

def get_current_span_id() -> Optional[str]:
    """
    获取当前 Span 栈顶的 Span ID。

    例如：

        trace
        └── node_A
            └── node_B

    在 node_B 内调用该函数：

        span_B

    在没有 Span 时：

        None
    """
    stack = _span_stack_var.get()

    if not stack:
        return None

    return stack[-1]


def push_span(span_id: str) -> contextvars.Token:
    """
    将 Span 压入当前 Context 的 Span 栈。

    返回 ContextVar Token，方便 finally 中恢复。
    """
    stack = _span_stack_var.get()

    new_stack = stack + (span_id,)

    return _span_stack_var.set(new_stack)

def reset_span_stack(token: contextvars.Token) -> None:
    """
    根据 Token 恢复进入 Span 之前的上下文。
    """
    _span_stack_var.reset(token)


# ============================================================
# 5. 时间工具
# ============================================================

def now_utc() -> datetime:
    """
    获取当前 UTC 时间。

    数据库建议统一保存 UTC 时间。
    """
    return datetime.now(timezone.utc)


def serialize_output(value: Any) -> Optional[str]:
    """
    将节点输出转换为 JSON 字符串。

    数据库中建议使用 TEXT / JSON 类型保存。

    如果对象无法 JSON 序列化，则退化为 str(value)。
    """
    if value is None:
        return None

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    except Exception:
        return str(value)

# ============================================================
# 7. Span 核心生命周期
# ============================================================

@asynccontextmanager
async def trace_span_context(
    node_name: str,
    span_type: str = "function",
):
    """
    异步 Span 上下文管理器。

    用法：

        async with trace_span_context("validator") as span_id:
            result = await validate(state)

    生命周期：

        获取 trace_id
              ↓
        生成 span_id
              ↓
        获取 parent_span_id
              ↓
        Span 入栈
              ↓
        INSERT running
              ↓
        执行业务代码
              ↓
        UPDATE success / error
              ↓
        Span 出栈
    """

    trace_id = get_trace_id()

    # 如果当前没有 Trace ID，
    # 说明当前代码可能不是从 API Trace 上下文进入。
    #
    # 这里不强制创建 Trace，因为 Trace 通常应该由 API
    # 入口统一创建。
    if trace_id is None:
        raise RuntimeError(
            f"Cannot create span '{node_name}' because "
            "no trace_id exists in current context."
        )

    span_id = generate_span_id()

    # 注意：
    # 必须在 push 之前获取 parent
    parent_span_id = get_current_span_id()

    start_time = now_utc()

    # 使用 monotonic 计算耗时。
    # datetime 不适合直接用于精确耗时计算，因为系统时间可能发生变化。
    start_monotonic = time.perf_counter()

    # Span 入栈
    stack_token = push_span(span_id)

    try:
        # ----------------------------------------------------
        # 写入 Span 开始状态
        # ----------------------------------------------------
        await insert_span_start(
            trace_id=trace_id,
            span_id=span_id,
            node_name=node_name,
            parent_span_id=parent_span_id,
            span_type=span_type,
            start_time=start_time,
        )

        # 把 span_id 暴露给调用者
        yield span_id

        # ----------------------------------------------------
        # 成功
        # ----------------------------------------------------
        end_time = now_utc()

        duration_ms = (
            time.perf_counter() - start_monotonic
        ) * 1000

        await update_span_end(
            span_id=span_id,
            end_time=end_time,
            duration_ms=duration_ms,
            status="success",
        )

    except Exception as exc:
        # ----------------------------------------------------
        # 异常
        # ----------------------------------------------------
        end_time = now_utc()

        duration_ms = (
            time.perf_counter() - start_monotonic
        ) * 1000

        try:
            await update_span_end(
                span_id=span_id,
                end_time=end_time,
                duration_ms=duration_ms,
                status="error",
                error=str(exc),
            )
        finally:
            # 非常重要：
            # 不吞掉业务异常
            raise

    finally:
        # ----------------------------------------------------
        # 恢复进入 Span 前的 Context
        # ----------------------------------------------------
        reset_span_stack(stack_token)


# ============================================================
# 8. @trace_span 装饰器
# ============================================================
def trace_span(
    node_name: str,
    span_type: str = "function",
):
    """
    自动追踪函数，同时支持同步与异步函数。

        @trace_span("validator")
        async def validator(state): ...

        @trace_span("normalize_itinerary")
        def _normalize_item(raw): ...   # 同步函数也能正确落 span，且返回值照常
    """

    def decorator(func: Callable[..., Any]):

        is_async = inspect.iscoroutinefunction(func)

        # ---- 统一的 Span 写入：兼容「循环运行中」与「无循环」两种场景 ----
        def _fire(coro: Awaitable[Any]) -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop is not None and loop.is_running():
                loop.create_task(coro)                      # 绝大多数情况走这里
            else:
                asyncio.new_event_loop().run_until_complete(coro)

        def _emit_start(trace_id, span_id, parent_span_id, start_time):
            _fire(
                insert_span_start(
                    trace_id=trace_id, span_id=span_id,
                    node_name=node_name, parent_span_id=parent_span_id,
                    span_type=span_type, start_time=start_time,
                )
            )

        def _emit_end(span_id, end_time, duration_ms, status, *, error=None, output=None):
            _fire(
                update_span_end(
                    span_id=span_id, end_time=end_time,
                    duration_ms=duration_ms, status=status,
                    error=error, output=output,
                )
            )

        # ===== 异步 wrapper（与原逻辑一致，仅把 await 读写收进 _emit_*） =====
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_id = get_trace_id()
            if trace_id is None:
                raise RuntimeError(
                    f"Cannot trace node '{node_name}' because "
                    "no trace_id exists in current context."
                )
            span_id = generate_span_id()
            parent_span_id = get_current_span_id()
            start_time = now_utc()
            start_monotonic = time.perf_counter()
            stack_token = push_span(span_id)
            try:
                _emit_start(trace_id, span_id, parent_span_id, start_time)
                result = await func(*args, **kwargs)
                _emit_end(
                    span_id, now_utc(),
                    (time.perf_counter() - start_monotonic) * 1000,
                    "success", output=result,
                )
                return result
            except Exception as exc:
                _emit_end(
                    span_id, now_utc(),
                    (time.perf_counter() - start_monotonic) * 1000,
                    "error", error=str(exc),
                )
                raise
            finally:
                reset_span_stack(stack_token)

        # ===== 同步 wrapper（新增） =====
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            trace_id = get_trace_id()
            if trace_id is None:
                raise RuntimeError(
                    f"Cannot trace node '{node_name}' because "
                    "no trace_id exists in current context."
                )
            span_id = generate_span_id()
            parent_span_id = get_current_span_id()
            start_time = now_utc()
            start_monotonic = time.perf_counter()
            stack_token = push_span(span_id)
            try:
                _emit_start(trace_id, span_id, parent_span_id, start_time)
                result = func(*args, **kwargs)             # 同步调用，不 await
                _emit_end(
                    span_id, now_utc(),
                    (time.perf_counter() - start_monotonic) * 1000,
                    "success", output=result,
                )
                return result
            except Exception as exc:
                _emit_end(
                    span_id, now_utc(),
                    (time.perf_counter() - start_monotonic) * 1000,
                    "error", error=str(exc),
                )
                raise
            finally:
                reset_span_stack(stack_token)

        return async_wrapper if is_async else sync_wrapper

    return decorator



# ============================================================
# 9. Trace 生命周期上下文
# ============================================================

@asynccontextmanager
async def trace_context(trace_id: Optional[str] = None):
    """
    创建一个完整 Trace 上下文。

    推荐在 API / Agent 请求入口使用：

        async with trace_context() as trace_id:
            result = await agent.run(state)

    如果没有传入 trace_id，则自动生成。
    """

    if trace_id is None:
        trace_id = generate_trace_id()

    trace_token = set_trace_id(trace_id)

    # 确保本次 Trace 不继承外层 Span
    stack_token = _span_stack_var.set(())

    try:
        yield trace_id

    finally:
        # 恢复进入 Trace 前的 Context
        _span_stack_var.reset(stack_token)
        _trace_id_var.reset(trace_token)