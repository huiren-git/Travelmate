import type { ExpenseCategory, GeneratedTripPlan, ItineraryCategory, ItineraryItem, TravelLogistics, TripSummary } from '../types/chat'

const expenseColors = ['#0071EB', '#FF6F61', '#10B981', '#F59E0B', '#8B5CF6', '#06B6D4']
const categoryLabels: ItineraryCategory[] = ['景酒', '餐饮', '交通', '娱乐', '其他']

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return String(value)
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
      const numberText = value.match(/-?\d+(\.\d+)?/)?.[0]
      if (!numberText) {
        continue
      }
      const normalized = Number(numberText)
      if (Number.isFinite(normalized)) {
        return normalized
      }
    }
  }
  return undefined
}

function hasPlanField(value: unknown) {
  if (!isRecord(value)) {
    return false
  }
  return Boolean(
    value.daily_itinerary ??
      value.draft_daily_itinerary ??
      value.itinerary ??
      value.plan ??
      value.budget ??
      value.draft_budget ??
      value.expenses ??
      value.cost,
  )
}

function getState(data: unknown) {
  if (!isRecord(data)) {
    return undefined
  }
  if (isRecord(data.state)) {
    return data.state
  }
  const nestedData = data.data ?? data.values
  if (isRecord(nestedData) && isRecord(nestedData.state)) {
    return nestedData.state
  }
  if (hasPlanField(nestedData)) {
    return nestedData as Record<string, unknown>
  }
  return data
}

function normalizeCategory(value: unknown): ItineraryCategory {
  const label = firstString(value) ?? ''
  const lower = label.toLowerCase()
  if (label.includes('餐') || label.includes('吃') || lower.includes('food')) return '餐饮'
  if (label.includes('车') || label.includes('交通') || lower.includes('transport')) return '交通'
  if (label.includes('娱乐') || label.includes('演出') || lower.includes('show')) return '娱乐'
  if (label.includes('景') || label.includes('游') || lower.includes('attraction')) return '景酒'
  return categoryLabels.includes(label as ItineraryCategory) ? (label as ItineraryCategory) : '其他'
}

function mapStatus(value: unknown) {
  const status = firstString(value)?.toLowerCase()
  if (status === 'completed' || status === '已完成') return '已完成'
  if (status === 'ongoing' || status === '已确认') return '已确认'
  return '待确认'
}

function formatPriceLabel(amount: number | undefined, estimateSource: string | undefined) {
  if (estimateSource === 'free') return '免费'
  if (amount === undefined) return '待估算'
  return estimateSource === 'rule' ? `规则估算 ¥${amount}` : `¥${amount}`
}

function extractItinerarySource(state: Record<string, unknown>) {
  return state.daily_itinerary ?? state.itinerary ?? state.plan
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
        firstString(item.timeRange, item.time_range, item.time, item.period) ??
        (start && end ? `${start} - ${end}` : '时间待定')
      const attractionName =
        firstString(
          item.attractionName,
          item.attraction_name,
          item.activity,
          item.name,
          item.place,
          item.location,
          item.title,
          item.address,
        ) ?? '待定行程'
      const imageUrl = firstString(item.image_url) ?? ''
      const tips = firstString(item.tips) ?? ''

      const price = firstNumber(item.priceCny, item.price, item.cost, item.amount, item.budget)
      const estimateSource = firstString(item.estimate_source, item.estimateSource)

      return {
        id: `${date}-${dayIndex}-${itemIndex}`,
        date,
        attractionName,
        timeRange,
        duration: firstString(item.duration),
        priceCny: price ?? 0,
        priceLabel: formatPriceLabel(price, estimateSource),
        status: mapStatus(item.status),
        imageUrl,
        category: normalizeCategory(item.category ?? item.type ?? item.cost_category ?? attractionName),
        tips: tips || undefined,
      }
    })
}

function normalizeItinerary(source: unknown) {
  return collectDayEntries(source).flatMap((day, dayIndex) => collectItemsFromDay(day, dayIndex))
}

function extractBudgetSource(state: Record<string, unknown>) {
  return state.budget ?? state.expenses ?? state.cost
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

  const detail = source.detail
  if (isRecord(detail)) {
    return normalizeExpenses(detail)
  }

  const categories = source.categories ?? source.items ?? source.breakdown ?? source.details
  if (Array.isArray(categories)) {
    return normalizeExpenses(categories)
  }

  return Object.entries(source)
    .filter(([key]) => !['level', 'total', 'total_budget', 'budgetCny', 'spentCny', 'saving_tips'].includes(key))
    .map(([key, value], index) => normalizeBudgetItem(value, index, categoryNameFromKey(key)))
    .filter((item): item is ExpenseCategory => Boolean(item))
}

function buildTitle(state: Record<string, unknown>) {
  const explicitTitle = firstString(state.title, state.trip_title, state.name)
  if (explicitTitle) {
    return explicitTitle
  }

  const destination = firstString(state.destination)
  const duration = firstNumber(state.duration)
  if (destination && duration) {
    return `${destination}${duration}日游`
  }
  return destination ? `${destination}旅行计划` : 'AI 规划行程'
}

function buildTripSummary(
  state: Record<string, unknown>,
  itinerary: ItineraryItem[],
  expensesByCategory: ExpenseCategory[],
): TripSummary | undefined {
  const budget = extractBudgetSource(state)
  if (!isRecord(budget)) {
    return undefined
  }

  const totalBudget = firstNumber(budget.total)
  if (totalBudget === undefined) {
    return undefined
  }

  const spentCny = expensesByCategory.reduce((sum, category) => sum + category.amount, 0)
  const firstDate = itinerary[0]?.date
  const lastDate = itinerary[itinerary.length - 1]?.date

  return {
    title: buildTitle(state),
    dateRange: firstDate && lastDate ? `${firstDate} - ${lastDate}` : firstString(state.dateRange, state.date_range) ?? '待确认',
    people: firstNumber(state.travelers, isRecord(state.structured_preferences) ? state.structured_preferences.travelers : undefined) ?? 1,
    budgetCny: totalBudget,
    spentCny,
  }
}

function normalizeLogistics(source: unknown): TravelLogistics | undefined {
  if (!isRecord(source) || !isRecord(source.accommodation)) return undefined
  const legs = Array.isArray(source.intercity_legs) ? source.intercity_legs : []
  const local = Array.isArray(source.local_transport_legs) ? source.local_transport_legs : []
  return {
    origin: firstString(source.origin), destination: firstString(source.destination) ?? '目的地', includeReturn: Boolean(source.include_return),
    intercityLegs: legs.filter(isRecord).map((leg) => ({ kind: firstString(leg.kind) ?? 'outbound', origin: firstString(leg.origin), destination: firstString(leg.destination) ?? '目的地', mode: firstString(leg.mode) ?? '待定', cost: firstNumber(leg.cost) ?? 0, status: firstString(leg.status) ?? 'pending', message: firstString(leg.message), estimateSource: firstString(leg.estimate_source) })),
    accommodation: { area: firstString(source.accommodation.area) ?? '待定', nights: firstNumber(source.accommodation.nights) ?? 0, rooms: firstNumber(source.accommodation.rooms) ?? 1, cost: firstNumber(source.accommodation.cost) ?? 0, status: firstString(source.accommodation.status) ?? 'estimated', level: firstString(source.accommodation.level) ?? 'mid', mode: firstString(source.accommodation.mode) === 'home' ? 'home' : 'hotel', estimateSource: firstString(source.accommodation.estimate_source) },
    localTransportLegs: local.filter(isRecord).map((leg) => ({ date: firstString(leg.date) ?? '', fromName: firstString(leg.from_name) ?? '上一站', toName: firstString(leg.to_name) ?? '下一站', mode: firstString(leg.mode) ?? '地铁', cost: firstNumber(leg.cost) ?? 0, distanceKm: firstNumber(leg.distance_km), durationMinutes: firstNumber(leg.duration_minutes), estimateSource: firstString(leg.estimate_source) })),
  }
}

export function adaptGeneratedTripPlan(data: unknown): GeneratedTripPlan | undefined {
  const state = getState(data)
  if (!state) {
    return undefined
  }

  if (state.terminal_status !== undefined && state.terminal_status !== 'confirmed') {
    return undefined
  }
  if (state.terminal_status === undefined && state.is_finished !== true) {
    return undefined
  }

  const budget = extractBudgetSource(state)
  if (!isRecord(budget)) {
    return undefined
  }

  const itinerary = normalizeItinerary(extractItinerarySource(state))
  if (itinerary.length === 0) {
    return undefined
  }

  const expensesByCategory = normalizeExpenses(budget)
  if (expensesByCategory.length === 0) {
    return undefined
  }

  const trip = buildTripSummary(state, itinerary, expensesByCategory)
  if (!trip) {
    return undefined
  }

  return {
    trip,
    itinerary,
    expensesByCategory,
    logistics: normalizeLogistics(state.travel_logistics),
  }
}
