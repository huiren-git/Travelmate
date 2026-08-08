import type { TravelHistory } from '../types/history'
import type { ProfileTravelStats } from '../types/profile'

function parseDate(value: string) {
  const [year, month, day] = value.split('.').map(Number)
  return Date.UTC(year, month - 1, day)
}

function getInclusiveDays(dateRange: string) {
  const [startDate, endDate] = dateRange.split(' - ')
  const millisecondsPerDay = 24 * 60 * 60 * 1000

  return Math.round((parseDate(endDate) - parseDate(startDate)) / millisecondsPerDay) + 1
}

export function getProfileTravelStats(histories: TravelHistory[]): ProfileTravelStats {
  return {
    tripCount: histories.length,
    visitedCityCount: new Set(histories.map((history) => history.destination)).size,
    totalDays: histories.reduce((total, history) => total + getInclusiveDays(history.dateRange), 0),
  }
}
