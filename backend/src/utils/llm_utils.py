"""LLM 调用与 JSON 响应解析工具。"""

import json
import re
from typing import Any


# 将 LangChain 消息或普通对象统一转换为文本内容。
def message_content(message: Any) -> str:
    return message.content if hasattr(message, "content") else str(message)


# 兼容同步和异步 LangChain 模型调用。
async def call_llm(llm: Any, messages: list[Any]) -> Any:
    if hasattr(llm, "ainvoke"):
        return await llm.ainvoke(messages)
    return llm.invoke(messages)


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
