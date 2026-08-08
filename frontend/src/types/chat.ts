export type ConversationStatus = '进行中' | '已完成'

export type ItineraryStatus = '已确认' | '待确认' | '已完成'

export type ItineraryCategory = '景酒' | '餐饮' | '交通' | '娱乐' | '其他'

export type Conversation = {
  id: string
  title: string
  updatedAt: string
  status: ConversationStatus
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

export type ItineraryItem = {
  id: string
  date: string
  attractionName: string
  timeRange: string
  priceCny: number
  status: ItineraryStatus
  imageUrl: string
  category: ItineraryCategory
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
