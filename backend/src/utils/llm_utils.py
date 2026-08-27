"""LLM 调用与 JSON 响应解析工具。"""

import json
import re
import asyncio
from datetime import datetime, timezone
import time
from typing import Any

from src.core.tracing import get_trace_id, get_current_span_id
from src.services.tracing_db import insert_llm_event
from src.core.tracing import trace_span


# 将 LangChain 消息或普通对象统一转换为文本内容。
def message_content(message: Any) -> str:
    return message.content if hasattr(message, "content") else str(message)


# 兼容同步和异步 LangChain 模型调用。
@trace_span("utils.llm_utils.call_llm", span_type="llm")
async def call_llm(llm: Any, messages: list[Any]) -> Any:
    """
    统一 LLM 调用入口，自动记录：
        - 调用时间
        - 耗时
        - Prompt（从 messages 提取）
        - Response
        - Token 消耗
    """
    # 1. 获取追踪上下文
    trace_id = get_trace_id()
    span_id = get_current_span_id()
    model_name = getattr(llm, "model_name", "unknown")
    
    # 2. 提取 Prompt 文本
    prompt_text = _extract_prompt_from_messages(messages)  # 需要实现
    
    # 3. 记录开始时间
    start_time = time.perf_counter()
    request_time = datetime.now(timezone.utc).isoformat()
    
    try:
        # 4. 执行真正的 LLM 调用
        if hasattr(llm, "ainvoke"):
            response = await llm.ainvoke(messages)
        else:
            response = llm.invoke(messages)
        
        # 5. 计算耗时并提取 Token
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        response_text = response.content if hasattr(response, "content") else str(response)
        usage = getattr(response, "usage_metadata", {}) or {}
        
        # 6. 异步写入 llm_events（不阻塞主流程）
        if trace_id and span_id:
            asyncio.create_task(
                insert_llm_event(
                    trace_id=trace_id,
                    span_id=span_id,
                    model_name=model_name,
                    request_time=request_time,
                    duration_ms=duration_ms,
                    prompt_text=prompt_text,
                    response_text=response_text,
                    prompt_tokens=usage.get("input_tokens"),
                    response_tokens=usage.get("output_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    status="success",
                )
            )
        
        return response
        
    except Exception as e:
        # 7. 记录异常
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        if trace_id and span_id:
            asyncio.create_task(
                insert_llm_event(
                    trace_id=trace_id,
                    span_id=span_id,
                    model_name=model_name,
                    request_time=request_time,
                    duration_ms=duration_ms,
                    prompt_text=prompt_text,
                    status="error",
                    error=str(e),
                )
            )
        raise


# 从模型输出中提取 JSON 对象或数组。
def extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return json.loads(fenced.group(1).strip())

    object_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    array_match = re.search(r"\[.*\]", text, flags=re.DOTALL)
    match = object_match or array_match
    if not match:
        raise ValueError("LLM response does not contain valid JSON")
    return json.loads(match.group(0))


# 确保模型输出是字典结构。
def ensure_dict(value: Any, field_name: str = "response") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


# 确保模型输出字段是列表结构。
def ensure_list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return value

def _extract_prompt_from_messages(messages: list[Any]) -> str:
    """
    从 LangChain 消息列表中提取人类可读的 Prompt 文本。
    """
    parts = []
    for msg in messages:
        role = getattr(msg, "type", "unknown")
        content = getattr(msg, "content", "")
        # 对特殊格式（如 SystemMessage）做标记
        if role == "system":
            parts.append(f"[System] {content}")
        elif role == "human":
            parts.append(f"[User] {content}")
        elif role == "ai":
            parts.append(f"[Assistant] {content}")
        else:
            parts.append(f"[{role}] {content}")
    return "\n".join(parts)
