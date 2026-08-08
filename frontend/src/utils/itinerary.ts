import type { ItineraryItem } from '../types/chat'

export function groupItineraryByDate(items: ItineraryItem[]) {
  const map: Record<string, ItineraryItem[]> = {}

  items.forEach((item) => {
    if (!map[item.date]) {
      map[item.date] = []
    }
    map[item.date].push(item)
  })

  return map
}
