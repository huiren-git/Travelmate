# Chat New Trip Empty State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ChatPage's New Trip button open a clean planning state with the requested middle-column slogan, input-only composer, and right-column empty state.

**Architecture:** Keep the feature in the existing ChatPage state flow. `useChatPageState` owns a boolean `isNewTripMode` plus actions that enter and exit it, while `ChatLayout` conditionally renders the middle and right content. Existing conversation and itinerary data remain unchanged, so selecting a stored conversation restores the current layout.

**Tech Stack:** React 19, TypeScript, Ant Design, TailwindCSS, existing ChatPage hooks/layouts/components.

---

### Task 1: Extend Chat page state with new-trip mode

**Files:**
- Modify: `src/hooks/useChatPageState.ts`

- [ ] **Step 1: Add the new-trip state and entry action**

Add `isNewTripMode` with an initial value of `false`, and add `startNewTrip` that sets the mode, clears the draft, clears `structuredPreferences`, and resets `selectedDateIndex`:

```ts
const [isNewTripMode, setIsNewTripMode] = useState(false)

function startNewTrip() {
  setIsNewTripMode(true)
  setDraft('')
  setStructuredPreferences(undefined)
  setSelectedDateIndex(0)
}
```

- [ ] **Step 2: Add explicit mode exit behavior**

Wrap conversation selection in a `selectConversation` function so selecting an existing conversation exits new-trip mode:

```ts
function selectConversation(conversationId: string) {
  setActiveConversationId(conversationId)
  setIsNewTripMode(false)
}
```

Set `isNewTripMode` to `false` after `sendMessage` accepts a non-empty draft, before appending the new messages.

- [ ] **Step 3: Return the new state and actions**

Return `isNewTripMode`, `selectConversation`, and `startNewTrip` from the hook so `ChatLayout` can pass them to child components. Keep the existing `setActiveConversationId` return only if no consumer requires replacement; otherwise replace it with `selectConversation` consistently in `ChatLayout`.

- [ ] **Step 4: Run the type/build check**

Run:

```powershell
npm run build
```

Expected: TypeScript and Vite complete successfully. The existing large-chunk warning may remain.

### Task 2: Wire New Trip into the conversation sidebar

**Files:**
- Modify: `src/components/chat/ConversationSider.tsx`
- Modify: `src/layouts/ChatLayout.tsx`

- [ ] **Step 1: Add the callback prop**

Extend `ConversationSiderProps` with:

```ts
onNewTrip: () => void
```

- [ ] **Step 2: Bind the New Trip button**

Add `onClick={onNewTrip}` to the existing New Trip button without changing its label, icon, width, or color styling.

- [ ] **Step 3: Pass the state action from ChatLayout**

Destructure `startNewTrip` from `ChatPageState` in `ChatLayout`, and pass it to `ConversationSider` as `onNewTrip`. Pass `selectConversation` as the conversation selection callback if Task 1 replaced the direct setter.

### Task 3: Add the middle-column new-trip empty state

**Files:**
- Create: `src/components/chat/NewTripEmptyState.tsx`
- Modify: `src/layouts/ChatLayout.tsx`

- [ ] **Step 1: Create the focused empty-state component**

Create a presentational component that renders the requested copy:

```tsx
export function NewTripEmptyState() {
  return (
    <section className="flex min-h-[45vh] items-start justify-center pt-[16vh] text-center">
      <div className="max-w-[680px] px-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          ✈️ 嘿，这次想去哪儿野
        </h1>
        <p className="mt-4 text-[15px] leading-7 text-slate-500">
          告诉我你的梦中情地、出行天数，剩下的交给我来折腾。预算、路线、吃喝玩乐，全都给你安排得明明白白～
        </p>
      </div>
    </section>
  )
}
```

The component must remain unframed so the current ChatInput is the only actionable surface in the middle column.

- [ ] **Step 2: Conditionally render middle content**

In `ChatLayout`, keep the existing scroll container and bottom composer. Replace the normal content block with:

```tsx
{isNewTripMode ? (
  <NewTripEmptyState />
) : (
  <>
    <TripSummaryCard conversationStatus={activeConversation.status} remaining={remaining} trip={trip} />
    <ChatMessages messages={messages} primaryColor={colors.primary} />
  </>
)}
```

Preserve the existing bottom padding so the doubled-height ChatInput remains unobscured.

### Task 4: Add the right-column empty state

**Files:**
- Modify: `src/components/itinerary/TripPlanSider.tsx`
- Modify: `src/layouts/ChatLayout.tsx`

- [ ] **Step 1: Add the empty-state prop**

Extend `TripPlanSiderProps` with:

```ts
isEmpty: boolean
```

- [ ] **Step 2: Render Ant Design Empty when requested**

Import `Empty` from `antd` and render the existing cards only when `isEmpty` is `false`:

```tsx
<div className="flex h-full items-center justify-center p-6">
  <Empty description="开启对话一起规划行程吧" />
</div>
```

Use Ant Design's built-in empty illustration so the right column shows an SVG without creating a custom decorative asset.

- [ ] **Step 3: Pass new-trip mode from ChatLayout**

Pass `isEmpty={isNewTripMode}` to `TripPlanSider`. Existing expense and itinerary props remain available for normal mode.

### Task 5: Verify the complete interaction

**Files:**
- Verify: `src/components/chat/ConversationSider.tsx`
- Verify: `src/components/chat/NewTripEmptyState.tsx`
- Verify: `src/layouts/ChatLayout.tsx`
- Verify: `src/components/itinerary/TripPlanSider.tsx`
- Verify: `src/hooks/useChatPageState.ts`

- [ ] **Step 1: Run the production build**

Run:

```powershell
npm run build
```

Expected: exit code `0`.

- [ ] **Step 2: Open the local ChatPage**

Use the running Vite page:

```text
http://127.0.0.1:5173/chat
```

- [ ] **Step 3: Verify New Trip entry behavior**

Confirm all of the following:

- Clicking `New Trip` clears the draft and the structured preference badge/state.
- The middle column hides the trip summary and conversation messages.
- The slogan appears near the upper third of the middle column with the exact requested title and copy.
- The input composer remains at the bottom.
- The right column hides expense and itinerary cards and shows the built-in empty SVG with `开启对话一起规划行程吧`.

- [ ] **Step 4: Verify recovery behavior**

Confirm that clicking an existing conversation restores the normal trip summary, chat messages, expense summary, and itinerary panel. Confirm that entering a non-empty message from the new-trip state exits the empty state after sending.

- [ ] **Step 5: Check the final diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated existing worktree changes remain untouched.
