# 出行与住宿模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为单目的地行程生成并展示城际交通、市内交通和全程单住宿据点，且预算可解释。

**Architecture:** 后端以 `travel_logistics` 聚合出行与住宿数据，预算代理只汇总该结构与活动费用。前端把该结构适配为独立物流卡片，并在行程项间显示对应的市内交通段。

**Tech Stack:** FastAPI、Python、LangGraph、pytest、React、TypeScript、Ant Design。

**Spec:** `docs/superpowers/specs/2026-08-27-travel-logistics-design.md`

## Global Constraints

- 仅支持单目的地与全程单住宿点。
- 所有新费用均为估算，未填出发地的城际交通不得计入总预算。
- 不增加第三方票务、酒店或地图路线依赖。

---

### Task 1: 物流领域模型和确定性计算

**Files:**
- Create: `backend/src/services/travel_logistics.py`
- Modify: `backend/src/graph/state.py`
- Test: `backend/tests/test_travel_logistics.py`

**Interfaces:**
- Produces: `build_travel_logistics(state, itinerary) -> dict`
- Consumes: `destination`、`origin`、`duration`、结构化交通与住宿偏好及每日行程。

- [ ] **Step 1: Write failing tests**，覆盖缺出发地的待补充城际段、往返段、全程单住宿和市内交通段。
- [ ] **Step 2: Run** `pytest tests/test_travel_logistics.py -v`，确认因模块不存在失败。
- [ ] **Step 3: Implement** 纯函数物流生成器和状态类型。
- [ ] **Step 4: Run** `pytest tests/test_travel_logistics.py -v`，确认通过。

### Task 2: 输入、行程生成和预算集成

**Files:**
- Modify: `backend/src/models/chat.py`
- Modify: `backend/src/utils/preferences_parser.py`
- Modify: `backend/src/api/v1/chat.py`
- Modify: `backend/src/agents/itinerary_agent.py`
- Modify: `backend/src/agents/budget_agent.py`
- Test: `backend/tests/test_budget_agent.py`

**Interfaces:**
- Consumes: `include_return`、`origin` 和 Task 1 的 `build_travel_logistics`。
- Produces: confirmed state 中的 `travel_logistics` 与五项预算明细。

- [ ] **Step 1: Write failing tests**，断言预算将城际/市内交通分开、住宿费用复用物流对象。
- [ ] **Step 2: Run** `pytest tests/test_budget_agent.py -v`，确认断言失败。
- [ ] **Step 3: Implement** 表单解析、初始状态及 itinerary/budget 节点集成。
- [ ] **Step 4: Run** `pytest tests/test_budget_agent.py tests/test_travel_logistics.py -v`，确认通过。

### Task 3: 前端输入与结果适配

**Files:**
- Modify: `frontend/src/types/chat.ts`
- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Modify: `frontend/src/utils/chatPlanAdapter.ts`
- Test: `frontend/src/utils/chatPlanAdapter.test.ts`

**Interfaces:**
- Consumes: 后端 `travel_logistics`。
- Produces: `GeneratedTripPlan.logistics` 与 `StructuredPreferences.origin/include_return`。

- [ ] **Step 1: Write failing adapter test**，断言服务端物流结构转为前端类型并保留 pending 状态。
- [ ] **Step 2: Run** 前端测试命令，确认适配器缺字段而失败。
- [ ] **Step 3: Implement** 类型、表单和适配器映射。
- [ ] **Step 4: Run** 前端测试及 `npm run build`。

### Task 4: 交通与住宿展示

**Files:**
- Create: `frontend/src/components/itinerary/TravelLogisticsCard.tsx`
- Modify: `frontend/src/layouts/ChatLayout.tsx`
- Modify: `frontend/src/components/itinerary/ItineraryPanel.tsx`
- Test: `frontend/src/utils/chatPlanAdapter.test.ts`

**Interfaces:**
- Consumes: `GeneratedTripPlan.logistics` 与每项 `localTransportLeg`。
- Produces: 全程住宿、城际交通、按天市内交通和行程卡内交通提示。

- [ ] **Step 1: Write failing adapter test**，断言市内交通段依日期可关联到行程项目。
- [ ] **Step 2: Run** 前端测试，确认失败。
- [ ] **Step 3: Implement** 物流卡片并挂入聊天布局与行程面板。
- [ ] **Step 4: Run** `npm run build`，确认 TypeScript 与生产构建通过。

### Task 5: 回归验证

**Files:**
- Modify: `backend/tests/test_travel_logistics.py`

- [ ] **Step 1: Add integration-shaped test**，构造两日北京行程并断言五项预算合计等于总额。
- [ ] **Step 2: Run** `pytest`。
- [ ] **Step 3: Run** `npm run build`。
- [ ] **Step 4: Review** `git diff --check` 与 `git status --short`。
