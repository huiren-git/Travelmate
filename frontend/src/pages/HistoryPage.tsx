import { HistoryLayout } from '../layouts/HistoryLayout'
import { useHistoryPageData } from '../hooks/useHistoryPageData'

export default function HistoryPage() {
  const historyPageData = useHistoryPageData()

  return <HistoryLayout {...historyPageData} />
}
