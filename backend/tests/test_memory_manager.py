import pytest
from langchain_core.messages import AIMessage


class FakeVectorStore:
    def __init__(self):
        self.add_calls = []
        self.search_calls = []

    def add_texts(self, texts, metadatas, ids):
        self.add_calls.append(
            {
                "texts": texts,
                "metadatas": metadatas,
                "ids": ids,
            }
        )

    def similarity_search_with_score(self, query, k, filter):
        self.search_calls.append({"query": query, "k": k, "filter": filter})
        document = type(
            "Document",
            (),
            {
                "page_content": "用户曾把长距离步行改成室内展览",
                "metadata": {"action_type": "replace"},
            },
        )()
        return [(document, 0.18)]


class FailingLLM:
    async def ainvoke(self, _):
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_log_user_action_persists_rag_document_with_inferred_preference(monkeypatch):
    from src.services import memory_manager

    stored = []

    async def fake_infer(action_type, original_content, new_content, user_reason):
        assert action_type == "replace"
        assert original_content == "南锣鼓巷"
        assert new_content == "北海公园散步"
        assert user_reason == "下午不想走太多路"
        return "用户倾向轻松、少步行的活动"

    async def fake_add_memory(user_id, text, memory_type, metadata):
        stored.append(
            {
                "user_id": user_id,
                "text": text,
                "memory_type": memory_type,
                "metadata": metadata,
            }
        )
        return "mem-action-1"

    monkeypatch.setattr(memory_manager, "_infer_preference_from_action", fake_infer)
    monkeypatch.setattr(memory_manager, "add_memory", fake_add_memory)

    memory_id = await memory_manager.log_user_action(
        user_id="user-1",
        thread_id="thread-1",
        action_type="replace",
        original_content="南锣鼓巷",
        new_content="北海公园散步",
        user_reason="下午不想走太多路",
    )

    assert memory_id == "mem-action-1"
    assert stored[0]["memory_type"] == "action"
    assert "推断偏好：用户倾向轻松、少步行的活动" in stored[0]["text"]
    assert stored[0]["metadata"]["thread_id"] == "thread-1"
    assert stored[0]["metadata"]["action_type"] == "replace"


@pytest.mark.asyncio
async def test_infer_preference_falls_back_when_lightweight_llm_fails(monkeypatch):
    from src.services import memory_manager

    monkeypatch.setattr(memory_manager, "get_llm", lambda **_: FailingLLM())

    preference = await memory_manager._infer_preference_from_action(
        "pace_change",
        "长距离步行",
        "咖啡馆休息",
        "今天太累了，不想走远",
    )

    assert preference == "用户倾向于轻松、短途的活动"


@pytest.mark.asyncio
async def test_action_memory_uses_current_vector_store_and_is_retrievable(monkeypatch):
    from src.services import memory_manager

    vectorstore = FakeVectorStore()
    monkeypatch.setattr(memory_manager.vector_store, "_action_vectorstore", vectorstore)

    memory_id = await memory_manager.add_memory(
        user_id="user-1",
        text="用户行程决策：把步行线路换成室内展览",
        memory_type="action",
        metadata={"thread_id": "thread-1"},
    )
    memories = await memory_manager.retrieve_memories(
        user_id="user-1",
        query="不想走太多路时怎么安排",
        memory_type="action",
        top_k=3,
    )

    assert memory_id.startswith("mem_")
    assert vectorstore.add_calls[0]["metadatas"][0]["memory_type"] == "action"
    assert vectorstore.search_calls == [
        {
            "query": "不想走太多路时怎么安排",
            "k": 3,
            "filter": {"user_id": "user-1"},
        }
    ]
    assert memories[0]["text"] == "用户曾把长距离步行改成室内展览"
