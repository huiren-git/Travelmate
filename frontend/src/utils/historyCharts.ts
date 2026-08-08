import type { CategoryExpense, DailyExpense } from '../types/history'

export function buildLineChartPoints(expenses: DailyExpense[], width = 560, height = 180, padding = 28) {
  if (expenses.length === 0) return ''

  const maxAmount = Math.max(...expenses.map((expense) => expense.amountCny), 1)
  const usableWidth = width - padding * 2
  const usableHeight = height - padding * 2

  return expenses
    .map((expense, index) => {
      const x = expenses.length === 1 ? width / 2 : padding + (index / (expenses.length - 1)) * usableWidth
      const y = height - padding - (expense.amountCny / maxAmount) * usableHeight
      return `${x},${y}`
    })
    .join(' ')
}

export function buildExpensePieGradient(categories: CategoryExpense[]) {
  const total = categories.reduce((sum, category) => sum + category.amountCny, 0)

  if (total <= 0) {
    return 'conic-gradient(#e5e7eb 0deg 360deg)'
  }

  let currentDeg = 0
  const segments = categories.map((category) => {
    const deg = (category.amountCny / total) * 360
    const start = currentDeg
    currentDeg += deg
    return `${category.color} ${start}deg ${currentDeg}deg`
  })

  return `conic-gradient(${segments.join(', ')})`
}
