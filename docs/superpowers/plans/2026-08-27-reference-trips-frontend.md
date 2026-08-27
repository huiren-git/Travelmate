# 参考行程前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reference-trip list and adoption UI that hands final adapted plans to the existing chat view.

**Architecture:** A focused API module owns list and SSE adoption transport. A new route renders cards and a parameter modal; React Router state transfers the done snapshot and adaptation log to the chat page, which reuses its existing itinerary adapter.

**Tech Stack:** React, TypeScript, React Router, Ant Design, Vite.

**Spec:** `docs/superpowers/specs/2026-08-27-reference-trips-frontend-design.md`

## Global Constraints

- Do not call the LLM from the browser; use only reference APIs.
- Navigate to `/chat` after successful adoption and reuse its existing itinerary UI.
- Preserve the current theme and i18n conventions.
- Display failure on the reference page and never navigate on an `error` SSE event.

---

### Task 1: Reference API transport and types

**Files:**
- Create: `frontend/src/api/reference.ts`
- Create: `frontend/src/types/reference.ts`

- [ ] **Step 1: Write a failing unit test for parsed reference SSE events.**
- [ ] **Step 2: Run the test and confirm it fails because the module is absent.**
- [ ] **Step 3: Implement `fetchReferenceTrips(page, pageSize)` and `adoptReference(id, request, onEvent)`, mirroring the complete-message buffering of `api/chat.ts`.**
- [ ] **Step 4: Run the unit test and confirm it passes.**
- [ ] **Step 5: Commit the API module and types.**

### Task 2: Reference list page and Home navigation

**Files:**
- Create: `frontend/src/pages/ReferenceTripsPage.tsx`
- Modify: `frontend/src/router/index.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`

- [ ] **Step 1: Write a failing render test asserting cards render reference destination/score and Home buttons navigate to `/reference`.**
- [ ] **Step 2: Run the test and confirm it fails because the route/page are absent.**
- [ ] **Step 3: Implement paginated cards, loading/empty/error states, and replace both Home “参考行程” coming-soon actions with `navigate('/reference')`.**
- [ ] **Step 4: Run the render test and confirm it passes.**
- [ ] **Step 5: Commit route and page navigation changes.**

### Task 3: Adoption modal and chat handoff

**Files:**
- Modify: `frontend/src/pages/ReferenceTripsPage.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/hooks/useChatPageState.ts`

- [ ] **Step 1: Write a failing test for successful SSE adoption carrying adaptation log and State to `/chat`.**
- [ ] **Step 2: Run the test and confirm it fails.**
- [ ] **Step 3: Implement date/duration/traveler modal, SSE progress/error handling, and route state handoff. Extend chat state to import the final snapshot once, update its itinerary panel, and add an assistant message summarizing adaptation entries.**
- [ ] **Step 4: Run the handoff test and Vite build; confirm both pass.**
- [ ] **Step 5: Commit the adoption handoff.**

### Task 4: Final verification

**Files:**
- Modify only files from Tasks 1–3 if verification reveals defects.

- [ ] **Step 1: Run `npm run build` in `frontend`.**
- [ ] **Step 2: Check `git diff --check` and review the changed-file diff.**
- [ ] **Step 3: Commit any verification-only corrections.**
