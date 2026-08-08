export type TravelStatus = '已完成' | '进行中' | '已归档'

export type HistoryOutletKey = 'route' | 'expense'

export type RouteTimelineItem = {
  id: string
  imageUrl: string
  attractionName: string
  time: string
  costCny: number
  description: string
}

export type DailyExpense = {
  date: string
  amountCny: number
}

export type CategoryExpense = {
  name: string
  amountCny: number
  color: string
}

export type ExpenseDetail = {
  id: string
  date: string
  title: string
  category: string
  amountCny: number
}

export type TravelHistory = {
  id: string
  destination: string
  title: string
  status: TravelStatus
  dateRange: string
  people: number
  coverImageUrl: string
  totalExpenseCny: number
  routeItems: RouteTimelineItem[]
  dailyExpenses: DailyExpense[]
  categoryExpenses: CategoryExpense[]
  expenseDetails: ExpenseDetail[]
}
