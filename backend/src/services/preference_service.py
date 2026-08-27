from __future__ import annotations

import logging
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from src.core.exceptions import raise_preference_tag_not_found
from src.models.preferences import (
    PreferenceCategory,
    PreferenceItem,
    PreferenceSummary,
)
from src.services.memory_manager import add_memory, delete_memory, retrieve_memories

logger = logging.getLogger("travelmate.services.preference_service")

_CATEGORY_KEYWORDS: dict[PreferenceCategory, tuple[str, ...]] = {
    "diet": ("吃", "餐", "辣", "海鲜", "美食"),
    "pace": ("累", "轻松", "早起", "步行", "节奏"),
    "budget": ("预算", "贵", "省", "价格", "花费"),
    "interest": ("历史", "文化", "自然", "购物", "艺术", "夜生活"),
    "accommodation": ("酒店", "住宿", "民宿"),
    "transport": ("地铁", "高铁", "飞机", "打车", "交通"),
}


class PreferenceService:
    """聚合手动偏好与记忆系统自动提取偏好。"""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, PreferenceItem]] = {}
        self._memory_ids: dict[str, dict[str, str]] = {}

    async def get_preferences(
        self,
        user_id: str,
        category: PreferenceCategory | None,
        include_inferred: bool,
    ) -> tuple[list[PreferenceItem], PreferenceSummary]:
        records = self._records.setdefault(user_id, {})
        for item in await self._load_persisted_preferences(user_id):
            records.setdefault(item.id, item)

        items = [item for item in records.values() if item.is_active]
        if category is not None:
            items = [item for item in items if item.category == category]
        if not include_inferred:
            items = [item for item in items if item.source == "manual"]
        items.sort(
            key=lambda item: (
                item.confidence,
                item.updated_at or item.created_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        categories: dict[str, int] = {}
        for item in items:
            categories[item.category] = categories.get(item.category, 0) + 1
        return items, PreferenceSummary(
            total=len(items),
            active_count=sum(item.is_active for item in items),
            categories=categories,
        )

    async def add(
        self,
        user_id: str,
        category: PreferenceCategory,
        content: str,
    ) -> PreferenceItem:
        now = datetime.now(timezone.utc)
        item = PreferenceItem(
            id=f"pref_{uuid4().hex[:12]}",
            category=category,
            content=content,
            source="manual",
            confidence=1.0,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self._records.setdefault(user_id, {})[item.id] = item
        memory_id = await self._persist_manual_preference(user_id, item)
        if memory_id:
            self._memory_ids.setdefault(user_id, {})[item.id] = memory_id
        return item

    async def update(
        self,
        user_id: str,
        preference_id: str,
        content: str,
    ) -> PreferenceItem:
        item = self._require_item(user_id, preference_id)
        now = datetime.now(timezone.utc)
        updated = item.model_copy(
            update={
                "content": content,
                "source": "manual",
                "confidence": 1.0,
                "is_active": True,
                "updated_at": now,
                "deleted_at": None,
            }
        )
        await self._delete_persisted_preference(user_id, preference_id)
        self._records[user_id][preference_id] = updated
        memory_id = await self._persist_manual_preference(user_id, updated)
        if memory_id:
            self._memory_ids.setdefault(user_id, {})[preference_id] = memory_id
        return updated

    async def delete(self, user_id: str, preference_id: str) -> PreferenceItem:
        item = self._require_item(user_id, preference_id)
        deleted = item.model_copy(
            update={
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._records[user_id][preference_id] = deleted
        await self._delete_persisted_preference(user_id, preference_id)
        return deleted

    async def replace_all_manual(
        self,
        user_id: str,
        items: list[tuple[PreferenceCategory, str]],
    ) -> list[PreferenceItem]:
        """整体替换用户的手动偏好：先删除现有全部 manual 偏好，再批量新增。

        推断偏好（来自 action 集合）不在此处管理，不受影响。
        """
        records = self._records.setdefault(user_id, {})
        # 先加载持久化偏好，填充 _memory_ids 映射，便于精确删除对应 Chroma 记忆。
        for item in await self._load_persisted_preferences(user_id):
            records.setdefault(item.id, item)

        manual_ids = [pid for pid, it in records.items() if it.source == "manual"]
        for pid in manual_ids:
            await self._delete_persisted_preference(user_id, pid)
            records.pop(pid, None)

        result: list[PreferenceItem] = []
        for category, content in items:
            result.append(await self.add(user_id, category, content))
        return result

    def _require_item(self, user_id: str, preference_id: str) -> PreferenceItem:
        item = self._records.get(user_id, {}).get(preference_id)
        if item is None:
            raise_preference_tag_not_found(tag_id=preference_id)
        return item

    async def _load_persisted_preferences(self, user_id: str) -> list[PreferenceItem]:
        try:
            memories = await retrieve_memories(
                user_id=user_id,
                query="用户旅行偏好",
                memory_type="preference",
                top_k=50,
            )
        except Exception:
            logger.exception("Failed to load inferred preferences")
            return []

        items = []
        for memory in memories:
            metadata = memory.get("metadata") if isinstance(memory.get("metadata"), dict) else {}
            content = str(memory.get("text") or "").strip()
            if not content:
                continue
            preference_id = str(
                metadata.get("preference_id")
                or f"pref_inferred_{sha256(content.encode('utf-8')).hexdigest()[:12]}"
            )
            category = metadata.get("category")
            if category not in _CATEGORY_KEYWORDS:
                category = self._infer_category(content)
            confidence = metadata.get("confidence", 0.7)
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = 0.7
            items.append(
                PreferenceItem(
                    id=preference_id,
                    category=category,
                    content=content.removeprefix("用户旅行偏好："),
                    source="manual" if metadata.get("source") == "manual" else "inferred",
                    confidence=confidence,
                    is_active=bool(metadata.get("is_active", True)),
                    created_at=metadata.get("created_at"),
                    updated_at=metadata.get("updated_at"),
                    deleted_at=metadata.get("deleted_at"),
                )
            )
            memory_id = metadata.get("memory_id")
            if memory_id:
                self._memory_ids.setdefault(user_id, {})[preference_id] = str(memory_id)
        return items

    async def _persist_manual_preference(self, user_id: str, item: PreferenceItem) -> str:
        try:
            memory_id = await add_memory(
                user_id=user_id,
                text=item.content,
                memory_type="preference",
                metadata={
                    "preference_id": item.id,
                    "category": item.category,
                    "source": item.source,
                    "confidence": item.confidence,
                    "is_active": item.is_active,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                },
            )
            if not memory_id:
                logger.warning("Manual preference was not persisted: preference_id=%s", item.id)
            return memory_id
        except Exception:
            logger.exception("Failed to persist manual preference: preference_id=%s", item.id)
            return ""

    async def _delete_persisted_preference(self, user_id: str, preference_id: str) -> None:
        memory_id = self._memory_ids.get(user_id, {}).pop(preference_id, None)
        if not memory_id:
            return
        if not await delete_memory(memory_id, user_id):
            logger.warning(
                "Manual preference memory was not deleted: preference_id=%s",
                preference_id,
            )

    @staticmethod
    def _infer_category(content: str) -> PreferenceCategory:
        for category, keywords in _CATEGORY_KEYWORDS.items():
            if any(keyword in content for keyword in keywords):
                return category
        return "interest"


preference_service = PreferenceService()
