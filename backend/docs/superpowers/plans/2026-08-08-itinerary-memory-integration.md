# Itinerary Agent Memory Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use relevant long-term preferences before itinerary generation and persist meaningful preference/action memories from the latest user request.

**Architecture:** Keep itinerary memory retrieval and message-derived candidate extraction inside `src/agents/itinerary_agent.py`. Add a small `/chat/resume` hook in `src/api/v1/chat.py` for explicit interrupt decisions that bypass the message history. Use async wrappers around `retrieve_memories` and `add_memory`, and ignore memory failures after logging so itinerary generation and resume remain available.

**Tech Stack:** Python 3.10+, pytest, pytest-asyncio, LangChain messages, existing Chroma-backed `memory_manager`.

---

### Task 1: Verify the red tests in the project virtual environment

**Files:**
- Test: `tests/test_itinerary_agent.py`

- [ ] **Step 1: Run only the new tests with the repository interpreter**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_itinerary_agent.py -k "retrieves_relevant_preferences or stores_preference_and_action_memories" -q
```

Expected: collection succeeds and tests fail because `_retrieve_relevant_preferences`, `_store_user_memory_candidates`, and `_add_memory` do not yet exist in `src/agents/itinerary_agent.py`.

### Task 2: Add memory helpers and prompt retrieval

**Files:**
- Modify: `src/agents/itinerary_agent.py`
- Test: `tests/test_itinerary_agent.py`

- [ ] **Step 1: Add lazy memory manager imports**

Use lazy imports so unit tests can replace the service functions without forcing vector-store initialization during module import:

```python
async def _retrieve_relevant_preferences(user_id: str, query: str) -> List[Dict[str, Any]]:
    try:
        from src.services.memory_manager import retrieve_memories
        return await retrieve_memories(
            user_id=user_id,
            query=query,
            memory_type="preference",
            top_k=5,
        )
    except Exception:
        logger.exception("Failed to retrieve user preferences")
        return []
```

- [ ] **Step 2: Extend `_state_payload` with retrieved preferences**

Add an optional `relevant_preferences` argument and include a JSON-safe list under the existing payload:

```python
def _state_payload(
    state: TravelAgentState,
    relevant_preferences: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    payload = {
        # existing fields...
        "relevant_preferences": relevant_preferences or [],
    }
```

- [ ] **Step 3: Pass retrieved preferences through `_build_itinerary_messages`**

Update `_build_itinerary_messages(state, relevant_preferences=None)` and call `_state_payload` with the retrieved list.

- [ ] **Step 4: Update `itinerary_agent_node` to retrieve before prompt construction**

Read the latest human message, retrieve preferences with that exact text, then call:

```python
response = await call_llm(
    llm,
    _build_itinerary_messages(state, relevant_preferences),
)
```

- [ ] **Step 5: Run the retrieval test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_itinerary_agent.py -k retrieves_relevant_preferences -q
```

Expected: PASS.

### Task 3: Persist semantic preference and action candidates

**Files:**
- Modify: `src/agents/itinerary_agent.py`
- Test: `tests/test_itinerary_agent.py`

- [ ] **Step 1: Add latest-message and candidate helpers**

Use the latest human message when available, and recognize explicit Chinese preference/action markers:

```python
PREFERENCE_MARKERS = ("喜欢", "偏好", "希望", "不喜欢", "不要太", "尽量", "优先", "适合")
ACTION_MARKERS = ("换成", "换一个", "改成", "调整", "重排", "取消", "删除", "别去", "不去", "接受", "拒绝")
```

Only non-empty messages containing a marker produce candidates. Preference candidates use `preference`, action candidates use `action`.

- [ ] **Step 2: Add async `_add_memory` wrapper**

Call existing `add_memory` with metadata containing `source`, `thread_id`, `plan_mode`, and a SHA-256 message fingerprint. Catch and log failures without raising.

- [ ] **Step 3: Add `_store_user_memory_candidates`**

For each candidate, call `_add_memory(user_id, text, memory_type, metadata)`. Store the original user text with a short semantic prefix so later retrieval retains context.

- [ ] **Step 4: Store candidates in `itinerary_agent_node`**

After reading the latest user message and before calling the LLM, await `_store_user_memory_candidates`.

- [ ] **Step 5: Run the storage test**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_itinerary_agent.py -k stores_preference_and_action_memories -q
```

Expected: PASS.

### Task 4: Persist explicit resume decisions

**Files:**
- Modify: `src/api/v1/chat.py`
- Test: `tests/test_chat_api.py`

- [ ] **Step 1: Write the failing resume-memory test**

Patch `test_resume_chat_uses_langgraph_command` to replace `_store_user_decision_memory` with a recorder and assert it receives the validated `user_id`, `thread_id`, and normalized decision dictionary.

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_chat_api.py -k resume_chat_uses_langgraph_command -q
```

Expected: FAIL because the resume-memory helper does not yet exist.

- [ ] **Step 3: Add the failure-isolated helper and call it after validation**

The helper lazily imports `add_memory`, stores an `action` memory containing the action, hint, and note, and catches/logs all storage errors. Call it only after `_ensure_owner` and interrupt validation succeed, immediately before starting the graph task.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_chat_api.py -k resume_chat_uses_langgraph_command -q
```

Expected: PASS.

### Task 5: Run the focused and full regression suites

**Files:**
- Modify: `src/agents/itinerary_agent.py`
- Modify: `src/api/v1/chat.py`
- Test: `tests/test_itinerary_agent.py`
- Test: `tests/test_chat_api.py`

- [ ] **Step 1: Run all itinerary tests**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_itinerary_agent.py -q
```

Expected: all itinerary tests pass.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Expected: no new failures. Tests requiring unavailable external services may skip according to existing fixtures.

- [ ] **Step 3: Inspect the final diff**

Run:

```powershell
git diff -- src/agents/itinerary_agent.py tests/test_itinerary_agent.py
git status --short
```

Confirm only the intended backend agent/test changes are part of the implementation; leave unrelated user changes untouched.
