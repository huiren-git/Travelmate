import { Layout } from 'antd'
import { HistoryDetailPanel } from '../components/history/HistoryDetailPanel'
import { TravelHistorySidebar } from '../components/history/TravelHistorySidebar'
import type { HistoryPageData } from '../hooks/useHistoryPageData'

const { Content } = Layout

type HistoryLayoutProps = HistoryPageData

export function HistoryLayout({ histories, selectedHistory, selectedHistoryId, setSelectedHistoryId }: HistoryLayoutProps) {
  return (
    <Content className="h-[calc(100vh-72px)] overflow-hidden">
      <div className="flex h-full">
        <TravelHistorySidebar histories={histories} onSelectHistory={setSelectedHistoryId} selectedHistoryId={selectedHistoryId} />
        <HistoryDetailPanel history={selectedHistory} />
      </div>
    </Content>
  )
}
