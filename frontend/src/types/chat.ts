export type ConversationStatus = '进行中' | '已完成' | '已停止'

export type ItineraryStatus = '已确认' | '待确认' | '已完成'

export type ItineraryCategory = '景酒' | '餐饮' | '交通' | '娱乐' | '其他'

export type Conversation = {
  id: string
  title: string
  updatedAt: string
  status: ConversationStatus
}

export type StructuredPreferences = {
  origin?: string
  include_return?: boolean
  start_date?: string
  budget_level?: '经济实惠' | '舒适出行' | '奢华体验'
  pace?: '轻松' | '适中' | '紧凑'
  interests?: string[]
  travelers?: number
  travelers_type?: '独自出行' | '情侣' | '亲子' | '朋友' | '家庭' | '长辈同行'
  hotel_preference?: '经济型酒店' | '舒适型酒店' | '高端酒店' | '特色民宿'
  lodging_mode?: 'hotel' | 'home'
  intercity_transport?: '火车' | '飞机' | '自驾' | '无偏好'
  local_transport?: '步行' | '公共交通' | '打车' | '网约车/专车' | '租车' | '无偏好'
}

export type TravelLogistics = {
  origin?: string
  destination: string
  includeReturn: boolean
  intercityLegs: Array<{ kind: string; origin?: string; destination: string; mode: string; cost: number; status: string; message?: string; estimateSource?: string }>
  accommodation: { area: string; nights: number; rooms: number; cost: number; status: string; level: string; mode?: 'hotel' | 'home'; estimateSource?: string }
  localTransportLegs: Array<{ date: string; fromName: string; toName: string; mode: string; cost: number; distanceKm?: number; durationMinutes?: number; estimateSource?: string }>
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
  structured_preferences?: StructuredPreferences
}

export type ItineraryItem = {
  id: string
  date: string
  attractionName: string
  timeRange: string
  duration?: string
  priceCny: number
  priceLabel?: string
  status: ItineraryStatus
  imageUrl: string
  category: ItineraryCategory
  tips?: string
}

export type ExpenseCategory = {
  name: string
  amount: number
  color: string
}

export type TripSummary = {
  title: string
  dateRange: string
  people: number
  budgetCny: number
  spentCny: number
}

export type GeneratedTripPlan = {
  trip: TripSummary
  itinerary: ItineraryItem[]
  expensesByCategory: ExpenseCategory[]
  logistics?: TravelLogistics
}
