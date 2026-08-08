import { useMemo, useState } from 'react'
import { travelHistories } from '../store/historyData'

export function useHistoryPageData() {
  const [selectedHistoryId, setSelectedHistoryId] = useState(travelHistories[0]?.id ?? '')

  const selectedHistory = useMemo(
    () => travelHistories.find((history) => history.id === selectedHistoryId) ?? travelHistories[0],
    [selectedHistoryId],
  )

  return {
    histories: travelHistories,
    selectedHistory,
    selectedHistoryId,
    setSelectedHistoryId,
  }
}

export type HistoryPageData = ReturnType<typeof useHistoryPageData>
