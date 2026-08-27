from datetime import datetime, timezone

import pytest

from src.models.common import ApiResponse
from src.models.preferences import (
    AddPreferenceRequest,
    PreferenceItem,
    ReplacePreferencesRequest,
    UpdatePreferenceRequest,
)


class FakePreferenceService:
    def __init__(self):
        self.item = PreferenceItem(
            id="pref_001",
            category="diet",
            content="不吃海鲜",
            source="manual",
            confidence=1.0,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        self.replaced_items: list[tuple[str, str]] = []

    async def add(self, user_id, category, content):
        return self.item

    async def update(self, user_id, preference_id, content):
        self.item = self.item.model_copy(update={"id": preference_id, "content": content})
        return self.item

    async def delete(self, user_id, preference_id):
        return self.item.model_copy(
            update={
                "id": preference_id,
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc),
            }
        )

    async def get_preferences(self, user_id, category, include_inferred):
        return [self.item], {
            "total": 1,
            "active_count": 1 if self.item.is_active else 0,
            "categories": {self.item.category: 1},
        }

    async def replace_all_manual(self, user_id, items):
        self.replaced_items = list(items)
        return [self.item for _ in items]


@pytest.mark.asyncio
async def test_preference_crud_uses_models_and_common_response(monkeypatch):
    from src.api.v1 import preferences as preferences_api

    service = FakePreferenceService()
    monkeypatch.setattr(preferences_api, "preference_service", service)

    created = await preferences_api.add_preference(
        AddPreferenceRequest(category="diet", content="不吃海鲜"),
        user_id="user-1",
    )
    updated = await preferences_api.update_preference(
        "pref_001",
        UpdatePreferenceRequest(content="喜欢川菜"),
        user_id="user-1",
    )
    deleted = await preferences_api.delete_preference("pref_001", user_id="user-1")
    listed = await preferences_api.get_preferences(
        category="diet",
        include_inferred=True,
        user_id="user-1",
    )

    assert isinstance(created, ApiResponse)
    assert created.code == 201
    assert created.data.category == "diet"
    assert updated.data.content == "喜欢川菜"
    assert deleted.data.is_active is False
    assert listed.data.preferences[0].category == "diet"


@pytest.mark.asyncio
async def test_replace_preferences_replaces_all_manual_and_returns_list(monkeypatch):
    from src.api.v1 import preferences as preferences_api

    service = FakePreferenceService()
    monkeypatch.setattr(preferences_api, "preference_service", service)

    response = await preferences_api.replace_preferences(
        ReplacePreferencesRequest(
            items=[
                {"category": "budget", "content": "舒适出行"},
                {"category": "transport", "content": "飞机"},
            ]
        ),
        user_id="user-1",
    )

    assert isinstance(response, ApiResponse)
    assert response.code == 200
    assert response.message == "偏好已更新"
    # service 收到的 items 顺序与请求一致
    assert service.replaced_items == [("budget", "舒适出行"), ("transport", "飞机")]
    # 返回的列表来自 get_preferences
    assert response.data.preferences[0].category == "diet"
