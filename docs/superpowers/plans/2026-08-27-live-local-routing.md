# 实时市内路线与方案确认 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用高德路线丰富市内交通段，并持久化住宿和城际交通的用户确认状态。

**Architecture:** `travel_logistics` 服务在已有的相邻景点成本基础上调用高德距离服务；失败时保留规则费用。确认接口将条目保存到 LangGraph 状态，并由物流构建器优先复用。

**Tech Stack:** FastAPI、LangGraph、httpx、高德地图 API、pytest、React、TypeScript、Ant Design。

**Spec:** `docs/superpowers/specs/2026-08-27-live-local-routing-design.md`

## Global Constraints

- 只调用已有高德地图 API，不新增酒店或票务服务。
- 高德失败必须回退到规则估算，不能阻断行程生成。
- 城际交通和住宿始终标识为规则估算。

---

### Task 1: 高德市内路线增强

**Files:**
- Modify: `backend/src/services/travel_logistics.py`
- Test: `backend/tests/test_travel_logistics.py`

**Interfaces:**
- Produces: `build_travel_logistics(state, itinerary) -> dict` 的 `local_transport_legs`，包含 `estimate_source`、距离与时长。

- [ ] **Step 1: Write failing async tests**：mock `amap_distance_km` 返回 1.5，断言交通段为 `amap`、距离为 1.5、时长大于零；mock 返回 `None`，断言保留 `rule` 与已有费用。
- [ ] **Step 2: Run** `PYTHONPATH=. pytest tests/test_travel_logistics.py -v`，确认新断言失败。
- [ ] **Step 3: Implement** async 路线增强函数，按交通方式估算时长，异常与空值均回退。
- [ ] **Step 4: Run** `PYTHONPATH=. pytest tests/test_travel_logistics.py -v`，确认通过。

### Task 2: 确认状态与接口

**Files:**
- Modify: `backend/src/graph/state.py`
- Modify: `backend/src/models/chat.py`
- Modify: `backend/src/api/v1/chat.py`
- Modify: `backend/src/services/travel_logistics.py`
- Test: `backend/tests/test_chat_api.py`

**Interfaces:**
- Produces: `POST /api/v1/chat/logistics/confirm`，请求 `{thread_id, item_key}`，返回最新 `travel_logistics`。

- [ ] **Step 1: Write failing API test**：确认 `accommodation` 后，响应中其状态为 `confirmed`，且同一 state 内保留确认项。
- [ ] **Step 2: Run** `PYTHONPATH=. pytest tests/test_chat_api.py -v`，确认新增用例失败。
- [ ] **Step 3: Implement** Pydantic 请求模型、状态确认写入、接口与物流恢复规则；未知 key 返回现有 40002 错误。
- [ ] **Step 4: Run** `PYTHONPATH=. pytest tests/test_chat_api.py -v`，确认通过。

### Task 3: 前端路线来源与确认操作

**Files:**
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/utils/chatPlanAdapter.ts`
- Modify: `frontend/src/components/itinerary/TravelLogisticsCard.tsx`
- Modify: `frontend/src/hooks/useChatPageState.ts`

**Interfaces:**
- Consumes: `POST /chat/logistics/confirm` 与后端 `estimate_source/status`。
- Produces: 卡片中的高德/规则标签、距离时长与确认按钮。

- [ ] **Step 1: Extend adapter types**：保留 `estimate_source`、距离、时长与确认状态。
- [ ] **Step 2: Implement confirmation request**：成功后以响应的物流结构更新当前生成行程。
- [ ] **Step 3: Render source/status**：市内段显示“高德路线”或“规则估算”；住宿、城际预估项显示确认按钮，已确认项显示标签。
- [ ] **Step 4: Run** `npm run build`，确认 TypeScript 和 Vite 构建通过。

### Task 4: 回归验证

**Files:**
- Test: `backend/tests/test_travel_logistics.py`
- Test: `backend/tests/test_chat_api.py`

- [ ] **Step 1: Run** `PYTHONPATH=. pytest -q`。
- [ ] **Step 2: Run** `npm run build`。
- [ ] **Step 3: Run** `git diff --check`，确认无空白错误。
