import pytest

from src.services import preference_service as preference_service_module
from src.services.preference_service import PreferenceService


@pytest.mark.asyncio
async def test_manual_preference_can_be_reloaded_from_memory(monkeypatch):
    stored_memories = []
    deleted_memory_ids = []

    async def fake_add_memory(user_id, text, memory_type, metadata):
        memory_id = f"mem_{len(stored_memories) + 1}"
        stored_memories.append(
            {
                "text": text,
                "metadata": {
                    **metadata,
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "memory_type": memory_type,
                },
            }
        )
        return memory_id

    async def fake_retrieve_memories(user_id, query, memory_type, top_k):
        return stored_memories

    async def fake_delete_memory(memory_id, user_id):
        deleted_memory_ids.append(memory_id)
        return True

    monkeypatch.setattr(preference_service_module, "add_memory", fake_add_memory)
    monkeypatch.setattr(
        preference_service_module,
        "retrieve_memories",
        fake_retrieve_memories,
    )
    monkeypatch.setattr(preference_service_module, "delete_memory", fake_delete_memory)

    writer = PreferenceService()
    created = await writer.add("user-1", "diet", "不吃海鲜")

    reader = PreferenceService()
    preferences, summary = await reader.get_preferences(
        "user-1",
        None,
        include_inferred=True,
    )

    assert [item.id for item in preferences] == [created.id]
    assert preferences[0].source == "manual"
    assert summary.active_count == 1

    await reader.delete("user-1", created.id)

    assert deleted_memory_ids == ["mem_1"]


@pytest.mark.asyncio
async def test_replace_all_manual_deletes_old_and_adds_new(monkeypatch):
    stored_memories: list[dict] = []
    deleted_memory_ids: list[str] = []

    async def fake_add_memory(user_id, text, memory_type, metadata):
        memory_id = f"mem_{len(stored_memories) + 1}"
        stored_memories.append(
            {
                "text": text,
                "metadata": {
                    **metadata,
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "memory_type": memory_type,
                },
            }
        )
        return memory_id

    async def fake_retrieve_memories(user_id, query, memory_type, top_k):
        # 模拟 Chroma 持久化：返回当前未被删除的记忆。
        return [m for m in stored_memories if m["metadata"].get("memory_id") not in deleted_memory_ids]

    async def fake_delete_memory(memory_id, user_id):
        deleted_memory_ids.append(memory_id)
        return True

    monkeypatch.setattr(preference_service_module, "add_memory", fake_add_memory)
    monkeypatch.setattr(preference_service_module, "retrieve_memories", fake_retrieve_memories)
    monkeypatch.setattr(preference_service_module, "delete_memory", fake_delete_memory)

    service = PreferenceService()
    # 先写入两条旧手动偏好
    old1 = await service.add("user-1", "diet", "不吃海鲜")
    old2 = await service.add("user-1", "interest", "摄影")
    assert len(stored_memories) == 2

    # 整体替换为新的三条
    result = await service.replace_all_manual(
        "user-1",
        [
            ("budget", "舒适出行"),
            ("transport", "飞机"),
            ("interest", "美食"),
        ],
    )

    # 旧的两条 Chroma 记忆被删除（memory_id 为 mem_1、mem_2）
    assert deleted_memory_ids == ["mem_1", "mem_2"]
    # 返回的是新写入的三条
    assert [item.content for item in result] == ["舒适出行", "飞机", "美食"]
    assert all(item.source == "manual" for item in result)

    # 重新读取，只剩新的三条手动偏好
    preferences, summary = await service.get_preferences("user-1", None, True)
    assert {item.content for item in preferences} == {"舒适出行", "美食", "飞机"}
    assert summary.active_count == 3
