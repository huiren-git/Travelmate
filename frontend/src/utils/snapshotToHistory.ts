import type {
  SessionItem,
  SessionSnapshotBlackboard,
  SnapshotBudgetDetail,
  SnapshotDayPlan,
} from '../api/sessions'
import type {
  CategoryExpense,
  DailyExpense,
  ExpenseDetail,
  RouteTimelineItem,
  TravelHistory,
  TravelStatus,
} from '../types/history'

// 后端 budget.detail 的类目键 → 前端展示名 + 饼图色
type CategoryMeta = { key: string; name: string; color: string }

const CATEGORY_META: CategoryMeta[] = [
  { key: 'transport', name: '交通/出行', color: '#10B981' },
  { key: 'hotel', name: '住宿/酒店', color: '#F59E0B' },
  { key: 'food', name: '餐饮/美食', color: '#FF6F61' },
  { key: 'tickets', name: '景点/门票', color: '#0071EB' },
]

function toTravelStatus(status: SessionItem['status']): TravelStatus {
  if (status === 'completed') return '已完成'
  if (status === 'deleted') return '已归档'
  return '进行中'
}

// "2026-08-17" → "8.17"
function shortDate(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getMonth() + 1}.${d.getDate()}`
}

// 列表阶段用 start_date + duration 推算日期区间
function listDateRange(start?: string | null, duration?: number | null): string {
  if (!start) return '日期待定'
  const s = new Date(start)
  if (Number.isNaN(s.getTime())) return start
  const days = duration && duration > 0 ? duration : 1
  const e = new Date(s)
  e.setDate(s.getDate() + days - 1)
  return `${shortDate(start)} - ${shortDate(e.toISOString())}`
}

function readTravelers(prefs: unknown): number {
  if (prefs && typeof prefs === 'object') {
    const travelers = (prefs as Record<string, unknown>).travelers
    if (typeof travelers === 'number' && travelers > 0) return travelers
  }
  return 1
}

// GET /sessions 返回的 SessionItem → 最小化 TravelHistory（仅列表展示所需字段）
export function mapSessionItemToTravelHistory(item: SessionItem): TravelHistory {
  return {
    id: item.thread_id,
    destination: item.destination ?? '未知目的地',
    title: `${item.destination ?? '旅行'}${item.duration ? `${item.duration}日游` : ''}`,
    status: toTravelStatus(item.status),
    dateRange: listDateRange(item.start_date, item.duration),
    people: 1,
    coverImageUrl: '',
    totalExpenseCny: 0,
    routeItems: [],
    dailyExpenses: [],
    categoryExpenses: [],
    expenseDetails: [],
  }
}

// 快照拉取前的占位条目（仅用于详情区加载态）
export function emptyTravelHistory(id: string): TravelHistory {
  return {
    id,
    destination: '未知目的地',
    title: '加载中…',
    status: '进行中',
    dateRange: '日期待定',
    people: 1,
    coverImageUrl: '',
    totalExpenseCny: 0,
    routeItems: [],
    dailyExpenses: [],
    categoryExpenses: [],
    expenseDetails: [],
  }
}

/**
 * 用 snapshot 的 blackboard 把“最小化 TravelHistory”补全为可渲染的详情。
 *
 * 数据真实性约定（与用户确认）：
 * - routeItems：来自 daily_itinerary，为真（逐项费用后端没有 → costCny 占位 0）
 * - categoryExpenses / totalExpenseCny：来自 budget，为真
 * - dailyExpenses：后端无按天拆分 → 按总额均摊占位
 * - expenseDetails：后端无逐笔明细 → 按类目各生成一条占位
 */
export function enrichTravelHistoryFromSnapshot(
  base: TravelHistory,
  blackboard: SessionSnapshotBlackboard,
): TravelHistory {
  const daily: SnapshotDayPlan[] | null = Array.isArray(blackboard.daily_itinerary)
    ? blackboard.daily_itinerary
    : Array.isArray(blackboard.draft_daily_itinerary)
      ? blackboard.draft_daily_itinerary
      : null
  const budget: SnapshotBudgetDetail | null = blackboard.budget ?? blackboard.draft_budget ?? null

  // 1. 行程轨迹：展平 daily_itinerary
  const routeItems: RouteTimelineItem[] = []
  if (daily) {
    daily.forEach((day) => {
      ;(day.items ?? []).forEach((item, idx) => {
        routeItems.push({
          id: `${base.id}-route-${day.day}-${idx}`,
          imageUrl: item.image_url || '',
          attractionName: item.activity || '未命名景点',
          time: `Day${day.day} ${item.time || ''}`.trim(),
          costCny: 0, // 后端无逐项费用，占位
          description: item.tips || item.address || '',
        })
      })
    })
  }

  // 2. 分类支出（饼图为真）
  const categoryExpenses: CategoryExpense[] = []
  if (budget && budget.detail) {
    for (const meta of CATEGORY_META) {
      const amount = budget.detail[meta.key]
      if (typeof amount === 'number' && amount > 0) {
        categoryExpenses.push({ name: meta.name, amountCny: Math.round(amount), color: meta.color })
      }
    }
  }

  const totalExpenseCny =
    budget && typeof budget.total === 'number' ? Math.round(budget.total) : 0

  // 3. 每日消费（折线图占位：按总额均摊到每天）
  const dailyExpenses: DailyExpense[] = []
  if (daily && daily.length && totalExpenseCny > 0) {
    const perDay = Math.round(totalExpenseCny / daily.length)
    daily.forEach((day, idx) => {
      const isLast = idx === daily.length - 1
      const amount = isLast ? totalExpenseCny - perDay * (daily.length - 1) : perDay
      dailyExpenses.push({ date: shortDate(day.date), amountCny: Math.max(0, amount) })
    })
  }

  // 4. 消费明细（占位：每类一条“预估”）
  const expenseDetails: ExpenseDetail[] = categoryExpenses.map((category, idx) => ({
    id: `${base.id}-expense-${idx}`,
    date: daily && daily[0] ? shortDate(daily[0].date) : '—',
    title: `${category.name}（预估）`,
    category: category.name,
    amountCny: category.amountCny,
  }))

  const people = readTravelers(blackboard.structured_preferences) ?? base.people
  const dateRange =
    daily && daily.length
      ? `${shortDate(daily[0].date)} - ${shortDate(daily[daily.length - 1].date)}`
      : base.dateRange

  return {
    ...base,
    people,
    dateRange,
    routeItems,
    categoryExpenses,
    totalExpenseCny,
    dailyExpenses,
    expenseDetails,
  }
}
