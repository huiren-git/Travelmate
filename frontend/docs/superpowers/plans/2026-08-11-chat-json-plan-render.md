# Chat JSON Plan Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render structured itinerary JSON from `/api/v1/chat/stream` into the existing ChatPage trip summary card and right itinerary sidebar instead of showing the raw JSON in chat messages.

**Architecture:** Add a tolerant frontend adapter that converts backend SSE payloads into the existing `TripSummary`, `ItineraryItem[]`, and `ExpenseCategory[]` UI models. Store adapted plans by `thread_id` in `useChatPageState()`, then return generated display data through the same props already consumed by `ChatLayout`, `TripSummaryCard`, and `TripPlanSider`.

**Tech Stack:** React, TypeScript, Vite, TailwindCSS, Ant Design, existing SSE helper `streamChat()`.

---

## File Structure

- Create: `src/utils/chatPlanAdapter.ts`
  - Owns all backend JSON shape detection, normalization, fallback values, and conversion into frontend chat UI models.
- Modify: `src/types/chat.ts`
  - Adds the `GeneratedTripPlan` type used by the adapter and hook state.
- Modify: `src/hooks/useChatPageState.ts`
  - Imports the adapter, stores generated plans per conversation/thread, clears the Empty state once a plan is parsed, and exposes generated display data through the existing return keys.
- No visual component changes are required unless TypeScript reveals a prop mismatch.

## Task 1: Add Generated Trip Type And Adapter

**Files:**
- Modify: `src/types/chat.ts`
- Create: `src/utils/chatPlanAdapter.ts`

- [ ] **Step 1: Run red static check**

Run:

```powershell
rg -n "GeneratedTripPlan|adaptGeneratedTripPlan" src
```

Expected: FAIL or no matches for `adaptGeneratedTripPlan`, proving the adapter does not exist yet.

- [ ] **Step 2: Add `GeneratedTripPlan` to `src/types/chat.ts`**

Append after `TripSummary`:

```ts
export type GeneratedTripPlan = {
  trip: TripSummary
  itinerary: ItineraryItem[]
  expensesByCategory: ExpenseCategory[]
}
```

- [ ] **Step 3: Create `src/utils/chatPlanAdapter.ts`**

Create this file:

```ts
import { itineraryImagePrompts } from '../assets/chatImagePrompts'
import type { ExpenseCategory, GeneratedTripPlan, ItineraryCategory, ItineraryItem, TripSummary } from '../types/chat'
import { img } from './image'

const expenseColors = ['#0071EB', '#FF6F61', '#10B981', '#F59E0B', '#8B5CF6', '#06B6D4']
const itineraryCategories: ItineraryCategory[] = ['景点', '餐饮', '交通', '娱乐', '其他']

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }
  return undefined
}

function firstNumber(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value
    }
    if (typeof value === 'string') {
      const normalized = Number(value.replace(/[^\d.-]/g, ''))
      if (Number.isFinite(normalized)) {
        return normalized
      }
    }
  }
  return undefined
}

function getState(data: unknown) {
  if (!isRecord(data)) {
    return undefined
  }
  if (isRecord(data.state)) {
    return data.state
  }
  if (isRecord(data.data) && isRecord(data.data.state)) {
    return data.data.state
  }
  return data
}

function normalizeCategory(value: unknown): ItineraryCategory {
  const label = firstString(value) ?? ''
  if (label.includes('餐') || label.includes('吃') || label.toLowerCase().includes('food')) return '餐饮'
  if (label.includes('车') || label.includes('交通') || label.toLowerCase().includes('transport')) return '交通'
  if (label.includes('娱乐') || label.includes('演出') || label.toLowerCase().includes('show')) return '娱乐'
  if (label.includes('景') || label.includes('游') || label.toLowerCase().includes('attraction')) return '景点'
  return itineraryCategories.includes(label as ItineraryCategory) ? (label as ItineraryCategory) : '其他'
}

function extractItinerarySource(state: Record<string, unknown>) {
  return state.daily_itinerary ?? state.draft_daily_itinerary ?? state.itinerary ?? state.plan
}

function collectDayEntries(source: unknown) {
  if (Array.isArray(source)) {
    return source
  }
  if (!isRecord(source)) {
    return []
  }

  const nested = source.days ?? source.daily_itinerary ?? source.items ?? source.schedule
  if (Array.isArray(nested)) {
    return nested
  }

  return Object.entries(source).map(([date, value]) => {
    if (isRecord(value)) {
      return { date, ...value }
    }
    return { date, items: value }
  })
}

function collectItemsFromDay(day: unknown, dayIndex: number) {
  if (!isRecord(day)) {
    return []
  }

  const date = firstString(day.date, day.day, day.title) ?? `Day ${dayIndex + 1}`
  const items = day.items ?? day.activities ?? day.attractions ?? day.places ?? day.schedule
  const itemList = Array.isArray(items) ? items : [day]

  return itemList
    .filter(isRecord)
    .map((item, itemIndex): ItineraryItem => {
      const start = firstString(item.start_time, item.startTime, item.start, item.begin)
      const end = firstString(item.end_time, item.endTime, item.end, item.finish)
      const timeRange =
        firstString(item.timeRange, item.time_range, item.time, item.period) ?? (start && end ? `${start} - ${end}` : '时间待定')
      const attractionName =
        firstString(item.attractionName, item.attraction_name, item.name, item.place, item.location, item.title, item.activity) ??
        '待定行程'

      return {
        id: `${date}-${dayIndex}-${itemIndex}`,
        date,
        attractionName,
        timeRange,
        priceCny: firstNumber(item.priceCny, item.price, item.cost, item.amount, item.budget) ?? 0,
        status: '待确认',
        imageUrl:
          firstString(item.imageUrl, item.image_url, item.image) ??
          img(`${itineraryImagePrompts.forbiddenCity}, ${attractionName}, realistic travel photo`, 'landscape_4_3'),
        category: normalizeCategory(item.category ?? item.type),
      }
    })
}

function normalizeItinerary(source: unknown) {
  return collectDayEntries(source).flatMap((day, dayIndex) => collectItemsFromDay(day, dayIndex))
}

function extractBudgetSource(state: Record<string, unknown>) {
  return state.budget ?? state.draft_budget ?? state.expenses ?? state.cost
}

function categoryNameFromKey(key: string) {
  const lower = key.toLowerCase()
  if (lower.includes('hotel') || key.includes('住宿')) return '住宿/酒店'
  if (lower.includes('food') || key.includes('餐') || key.includes('美食')) return '餐饮/美食'
  if (lower.includes('transport') || key.includes('交通')) return '交通/出行'
  if (lower.includes('ticket') || key.includes('门票') || key.includes('景点')) return '景点/门票'
  return key
}

function normalizeBudgetItem(value: unknown, index: number, fallbackName: string): ExpenseCategory | undefined {
  if (isRecord(value)) {
    const name = firstString(value.name, value.category, value.type, value.label) ?? fallbackName
    const amount = firstNumber(value.amount, value.cost, value.price, value.value, value.total) ?? 0
    if (amount > 0) {
      return { name, amount, color: expenseColors[index % expenseColors.length] }
    }
    return undefined
  }

  const amount = firstNumber(value)
  return amount && amount > 0
    ? { name: fallbackName, amount, color: expenseColors[index % expenseColors.length] }
    : undefined
}

function normalizeExpenses(source: unknown) {
  if (Array.isArray(source)) {
    return source
      .map((item, index) => normalizeBudgetItem(item, index, `预算 ${index + 1}`))
      .filter((item): item is ExpenseCategory => Boolean(item))
  }

  if (!isRecord(source)) {
    return []
  }

  const categories = source.categories ?? source.items ?? source.breakdown ?? source.details
  if (Array.isArray(categories)) {
    return normalizeExpenses(categories)
  }

  return Object.entries(source)
    .filter(([key]) => !['total', 'total_budget', 'budgetCny', 'spentCny'].includes(key))
    .map(([key, value], index) => normalizeBudgetItem(value, index, categoryNameFromKey(key)))
    .filter((item): item is ExpenseCategory => Boolean(item))
}

function buildTripSummary(state: Record<string, unknown>, itinerary: ItineraryItem[], expensesByCategory: ExpenseCategory[]): TripSummary {
  const budget = extractBudgetSource(state)
  const totalBudget = isRecord(budget)
    ? firstNumber(budget.total, budget.total_budget, budget.budgetCny, budget.amount)
    : firstNumber(budget)
  const spentCny = expensesByCategory.reduce((sum, category) => sum + category.amount, 0)
  const firstDate = itinerary[0]?.date
  const lastDate = itinerary[itinerary.length - 1]?.date

  return {
    title: firstString(state.title, state.trip_title, state.name, state.destination) ?? 'AI 规划行程',
    dateRange: firstDate && lastDate ? `${firstDate} - ${lastDate}` : firstString(state.dateRange, state.date_range) ?? '待确认',
    people: firstNumber(state.travelers, isRecord(state.structured_preferences) ? state.structured_preferences.travelers : undefined) ?? 1,
    budgetCny: totalBudget ?? spentCny,
    spentCny,
  }
}

export function adaptGeneratedTripPlan(data: unknown): GeneratedTripPlan | undefined {
  const state = getState(data)
  if (!state) {
    return undefined
  }

  const itinerary = normalizeItinerary(extractItinerarySource(state))
  if (itinerary.length === 0) {
    return undefined
  }

  const expensesByCategory = normalizeExpenses(extractBudgetSource(state))
  const trip = buildTripSummary(state, itinerary, expensesByCategory)

  return {
    trip,
    itinerary,
    expensesByCategory,
  }
}
```

- [ ] **Step 4: Run green static check**

Run:

```powershell
rg -n "GeneratedTripPlan|adaptGeneratedTripPlan" src
```

Expected: matches in `src/types/chat.ts` and `src/utils/chatPlanAdapter.ts`.

## Task 2: Store And Expose Generated Plans In Chat State

**Files:**
- Modify: `src/hooks/useChatPageState.ts`

- [ ] **Step 1: Import adapter and type**

Change the imports to include:

```ts
import type { ChatMessage, Conversation, GeneratedTripPlan, StructuredPreferences } from '../types/chat'
import { adaptGeneratedTripPlan } from '../utils/chatPlanAdapter'
```

- [ ] **Step 2: Add generated-plan state**

Place this beside the other `useState()` calls:

```ts
const [generatedTripPlansByConversationId, setGeneratedTripPlansByConversationId] = useState<
  Record<string, GeneratedTripPlan>
>({})
```

- [ ] **Step 3: Derive display data from generated plan first**

Replace the existing trip/sidebar derivations with:

```ts
const generatedTripPlan = generatedTripPlansByConversationId[activeConversationId]
const displayTrip = generatedTripPlan?.trip ?? trip
const displayItinerary = generatedTripPlan?.itinerary ?? itinerary
const displayExpensesByCategory = generatedTripPlan?.expensesByCategory ?? expensesByCategory
const isTripPlanEmpty = emptyTripPlanConversationIds.has(activeConversationId) && !generatedTripPlan
const isActiveConversationEmpty = messages.length === 0
const showNewTripEmptyState = isTripPlanEmpty && isActiveConversationEmpty

const itineraryGroupedByDate = useMemo(() => groupItineraryByDate(displayItinerary), [displayItinerary])
const datesList = useMemo(() => Object.keys(itineraryGroupedByDate), [itineraryGroupedByDate])
const activeDate = datesList[selectedDateIndex] || datesList[0] || ''
const currentItems = itineraryGroupedByDate[activeDate] || []
const remaining = Math.max(0, displayTrip.budgetCny - displayTrip.spentCny)
const pieConicGradient = useMemo(() => buildPieConicGradient(displayExpensesByCategory), [displayExpensesByCategory])
```

- [ ] **Step 4: Reset selected date when switching conversations or starting new trip**

Update `selectConversation()`:

```ts
function selectConversation(conversationId: string) {
  setActiveConversationId(conversationId)
  setIsNewTripMode(false)
  setSelectedDateIndex(0)
}
```

Keep the existing `setSelectedDateIndex(0)` in `startNewTrip()`.

- [ ] **Step 5: Adapt every SSE payload before updating message text**

At the start of the `streamChat()` callback, insert:

```ts
const generatedTripPlan = adaptGeneratedTripPlan(event.data)
if (generatedTripPlan) {
  setGeneratedTripPlansByConversationId((current) => ({
    ...current,
    [threadId]: generatedTripPlan,
  }))
  setEmptyTripPlanConversationIds((current) => {
    const next = new Set(current)
    next.delete(threadId)
    return next
  })
}
```

Then keep the existing `streamEventContent(event)` flow:

```ts
const nextContent = streamEventContent(event)
if (!nextContent) {
  return
}
```

- [ ] **Step 6: Return display data through existing keys**

Change the return object values:

```ts
expensesByCategory: displayExpensesByCategory,
pieConicGradient,
remaining,
trip: displayTrip,
```

Keep `currentItems`, `datesList`, `activeDate`, and `isTripPlanEmpty` as derived above.

## Task 3: Verify Chat Layout Still Uses Existing Components

**Files:**
- Read: `src/layouts/ChatLayout.tsx`

- [ ] **Step 1: Confirm no raw JSON render path was added**

Run:

```powershell
rg -n "JSON.stringify|adaptGeneratedTripPlan|GeneratedTripPlan" src/layouts src/components
```

Expected: no matches in layout/components, because JSON adaptation stays in `src/utils/chatPlanAdapter.ts` and `src/hooks/useChatPageState.ts`.

- [ ] **Step 2: Confirm generated state reaches right sidebar through current props**

Run:

```powershell
rg -n "TripSummaryCard|TripPlanSider|expensesByCategory|currentItems|trip=|spentCny" src/layouts/ChatLayout.tsx
```

Expected: `TripSummaryCard` receives `trip={trip}` and `remaining={remaining}`; `TripPlanSider` receives `currentItems`, `expensesByCategory`, `pieConicGradient`, and `spentCny={trip.spentCny}`.

## Task 4: Build Verification

**Files:**
- Verify: full frontend project

- [ ] **Step 1: Run TypeScript and Vite build**

Run:

```powershell
npm run build
```

Expected: command exits `0`. Vite may print the existing large chunk warning.

- [ ] **Step 2: Run diff whitespace check**

Run:

```powershell
git diff --check -- src/types/chat.ts src/utils/chatPlanAdapter.ts src/hooks/useChatPageState.ts
```

Expected: exit `0`, or only the existing Windows line-ending warning that does not point to a new whitespace error.

- [ ] **Step 3: Manual browser check**

Use the running Vite page or start it with:

```powershell
npm run dev
```

Send a trip planning message that returns structured itinerary JSON. Confirm:

- The assistant bubble shows natural AI text when the backend sends `messages`.
- The raw itinerary JSON is not dumped into the chat bubble.
- The middle column shows the generated summary card above chat messages.
- The right column switches from Empty to generated budget and itinerary entries.
- Switching conversations keeps each thread's generated plan isolated.

