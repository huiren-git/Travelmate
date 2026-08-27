import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from src.core.tracing import trace_span, trace_span_context
from src.agents.base import get_llm
from src.services import vector_store
from src.utils.llm_utils import call_llm, message_content

logger = logging.getLogger("travelmate.services.memory_manager")

MemoryType = Literal["preference", "action"]
ActionType = Literal["delete", "replace", "add", "pace_change", "confirm", "replan"]


class UserActionLog(BaseModel):
    """可写入 action 向量集合的结构化用户操作日志。"""

    user_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    action_type: ActionType
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    user_reason: str = ""
    inferred_preference: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _vectorstore_for(memory_type: MemoryType):
    if memory_type == "preference":
        return vector_store._pref_vectorstore
    return vector_store._action_vectorstore


def _fallback_preference(reason: str) -> str:
    if any(keyword in reason for keyword in ("累", "远", "走", "步行")):
        return "用户倾向于轻松、短途的活动"
    if any(keyword in reason for keyword in ("雨", "晒", "热", "冷")):
        return "用户会根据天气调整活动"
    if any(keyword in reason for keyword in ("贵", "预算", "便宜", "省")):
        return "用户对旅行预算较敏感"
    return "用户对行程进行了个性化调整"


async def _infer_preference_from_action(
    action_type: str,
    original_content: str,
    new_content: str,
    user_reason: str,
) -> str:
    """用轻量级 LLM 从一次行程调整中提炼可复用的偏好。"""

    prompt = f"""
用户正在修改旅行行程：
- 操作类型：{action_type}
- 原计划：{original_content or "无"}
- 调整为：{new_content or "无"}
- 用户原话：{user_reason or "无"}

请用一句简洁的话（不超过20字），推断用户潜在的旅行偏好或禁忌。
只输出推断结果，不要输出其他内容。
""".strip()
    try:
        llm = get_llm(model_string="qwen:qwen-flash", temperature=0.1)
        response = await call_llm(llm, [HumanMessage(content=prompt)])
        preference = message_content(response).strip()
        return preference[:20] if preference else _fallback_preference(user_reason)
    except Exception as exc:
        logger.warning("偏好推断失败: %s，使用规则降级", exc)
        return _fallback_preference(user_reason)


async def log_user_action(
    user_id: str,
    thread_id: str,
    action_type: ActionType,
    original_content: Optional[str],
    new_content: Optional[str],
    user_reason: str,
) -> str:
    """记录结构化行程操作，并写入 action RAG 集合。"""

    inferred_preference = await _infer_preference_from_action(
        action_type,
        original_content or "",
        new_content or "",
        user_reason,
    )
    action_log = UserActionLog(
        user_id=user_id,
        thread_id=thread_id,
        action_type=action_type,
        original_content=original_content,
        new_content=new_content,
        user_reason=user_reason,
        inferred_preference=inferred_preference,
    )
    log_text = (
        f"用户执行了 {action_log.action_type} 操作。"
        f"原计划：{action_log.original_content or '无'}。"
        f"调整为：{action_log.new_content or '无'}。"
        f"用户原因：{action_log.user_reason or '未说明'}。"
        f"推断偏好：{action_log.inferred_preference}"
    )
    metadata = {
        "thread_id": action_log.thread_id,
        "action_type": action_log.action_type,
        "timestamp": action_log.timestamp.isoformat(),
        "inferred_preference": action_log.inferred_preference,
    }
    doc_id = await add_memory(
        user_id=action_log.user_id,
        text=log_text,
        memory_type="action",
        metadata=metadata,
    )
    logger.info("操作日志已记录: %s -> %s", action_log.action_type, doc_id)
    return doc_id


async def add_memory(
    user_id: str,
    text: str,
    memory_type: MemoryType = "preference",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """存储一条偏好记忆或操作日志。"""

    if not user_id or not text.strip():
        return ""
    vectorstore_instance = _vectorstore_for(memory_type)
    if vectorstore_instance is None:
        logger.error("向量存储未初始化: memory_type=%s", memory_type)
        return ""

    meta = dict(metadata or {})
    meta["user_id"] = user_id
    meta["memory_type"] = memory_type
    doc_id = f"mem_{uuid.uuid4().hex[:12]}"
    meta["memory_id"] = doc_id
    vectorstore_instance.add_texts(
        texts=[text],
        metadatas=[meta],
        ids=[doc_id],
    )
    logger.info("记忆已存储: %s | user=%s | id=%s", memory_type, user_id, doc_id)
    return doc_id

async def retrieve_memories(
    user_id: str,
    query: str,
    memory_type: MemoryType = "preference",
    top_k: int = 5,
) -> List[Dict[str, Any]]:

    if not user_id or not query.strip() or top_k <= 0:
        return []
    
    vectorstore_instance = _vectorstore_for(memory_type)
    if vectorstore_instance is None:
        return []

    try:
        async with trace_span_context("memory_retrieve", "io"):
            results = vectorstore_instance.similarity_search_with_score(
                query=query,
                k=top_k,
                filter={"user_id": user_id},
            )
    except Exception as e:
        # 即使追踪失败，也不应影响主流程
        # 但这里已经包裹在 try 中，异常会被捕获并记录
        logger.error(f"记忆检索失败: {e}")
        return []

    memories = [
        {
            "text": doc.page_content,
            "metadata": doc.metadata,
            "score": score,
        }
        for doc, score in results
    ]
    logger.info("检索到 %s 条 %s 记忆", len(memories), memory_type)
    return memories


async def delete_memory(memory_id: str, user_id: str) -> bool:
    """删除指定用户的记忆。"""

    try:
        for memory_type in ("preference", "action"):
            vectorstore_instance = _vectorstore_for(memory_type)
            if vectorstore_instance is not None:
                vectorstore_instance.delete(ids=[memory_id])
        logger.info("记忆已删除: %s | user=%s", memory_id, user_id)
        return True
    except Exception as exc:
        logger.error("删除记忆失败: %s", exc)
        return False
