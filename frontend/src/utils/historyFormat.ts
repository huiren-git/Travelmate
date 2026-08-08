import type { TravelStatus } from '../types/history'

export function formatCurrencyCny(amount: number) {
  return `¥${amount.toLocaleString('zh-CN')}`
}

export function formatPeopleCount(people: number) {
  return `${people} 人出行`
}

export function getTravelStatusColor(status: TravelStatus) {
  if (status === '已完成') return 'green'
  if (status === '进行中') return 'processing'
  return 'default'
}
