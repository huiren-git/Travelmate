import type { TravelHistory } from '../types/history'
import type { ProfileTravelStats } from '../types/profile'

// 兼容 "2026.7.12" 与 "7.12"（无年份按当前年补全）；非法/缺值返回 null
function parseDate(value: string): number | null {
  if (!value || typeof value !== 'string') return null
  const parts = value.split('.').map(Number)
  if (parts.some((n) => Number.isNaN(n))) return null

  let year: number
  let month: number
  let day: number
  if (parts.length === 3) {
    ;[year, month, day] = parts
  } else if (parts.length === 2) {
    year = new Date().getFullYear()
    ;[month, day] = parts
  } else {
    return null
  }

  const timestamp = Date.UTC(year, month - 1, day)
  return Number.isNaN(timestamp) ? null : timestamp
}

function getInclusiveDays(dateRange: string): number {
  if (!dateRange || dateRange === '日期待定') return 0
  const [startPart, endPart] = dateRange.split(' - ')
  if (!startPart || !endPart) return 0

  const start = parseDate(startPart)
  const end = parseDate(endPart)
  if (start == null || end == null) return 0

  const millisecondsPerDay = 24 * 60 * 60 * 1000
  const days = Math.round((end - start) / millisecondsPerDay) + 1
  return days > 0 ? days : 0
}

export function getProfileTravelStats(histories: TravelHistory[]): ProfileTravelStats {
  return {
    tripCount: histories.length,
    visitedCityCount: new Set(histories.map((history) => history.destination)).size,
    totalDays: histories.reduce((total, history) => total + getInclusiveDays(history.dateRange), 0),
  }
}
