# Chat Structured Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a quick-plan modal to the chat composer and include saved structured preferences with outgoing user messages.

**Architecture:** Define a serializable `StructuredPreferences` type in the chat domain. Keep the value in `useChatPageState`, pass it through `ChatLayout`, and use `ChatInput` to edit it with Ant Design form controls.

**Tech Stack:** React 19, TypeScript, Ant Design 6, Tailwind CSS, Vite.

---

### Task 1: Add Structured Preference State

**Files:**
- Modify: `src/types/chat.ts`
- Modify: `src/hooks/useChatPageState.ts`

- [ ] Add a `StructuredPreferences` type with optional fields: `budget_level`, `pace`, `interests`, `travelers`, `travelers_type`, `hotel_preference`, `intercity_transport`, and `local_transport`.
- [ ] Add optional `structured_preferences` to `ChatMessage`.
- [ ] Create `structuredPreferences` state in `useChatPageState`, expose its setter, and attach the value to each outgoing user message.

### Task 2: Add the Quick-Plan Modal

**Files:**
- Modify: `src/components/chat/ChatInput.tsx`
- Modify: `src/layouts/ChatLayout.tsx`

- [ ] Pass the structured preference value and setter through `ChatLayout`.
- [ ] Increase the textarea minimum height to four rows and reserve space for both in-input controls.
- [ ] Add a lower-left checklist icon button that opens a centered `Modal`.
- [ ] Build an optional Ant Design `Form` with radio groups, checkbox groups, selects, and an input number for all requested fields.
- [ ] Save non-empty values to chat state and keep them available for later messages.

### Task 3: Verify

**Files:**
- Verify only

- [ ] Run `npm run build` and confirm TypeScript compilation plus Vite bundling complete with exit code 0.
- [ ] Open the quick-plan modal, save values, reopen it to confirm persistence, then send a message and inspect the in-memory user message payload.
