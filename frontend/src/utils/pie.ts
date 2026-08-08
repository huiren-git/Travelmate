import type { ExpenseCategory } from '../types/chat'

export function buildPieConicGradient(categories: ExpenseCategory[]) {
  const total = categories.reduce((sum, category) => sum + category.amount, 0)

  if (total <= 0) {
    return 'conic-gradient(#e5e7eb 0deg 360deg)'
  }

  let currentDeg = 0
  const segments = categories.map((category) => {
    const deg = (category.amount / total) * 360
    const start = currentDeg
    currentDeg += deg
    return `${category.color} ${start}deg ${currentDeg}deg`
  })

  return `conic-gradient(${segments.join(', ')})`
}
