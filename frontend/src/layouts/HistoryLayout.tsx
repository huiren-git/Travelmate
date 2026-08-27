import { Layout } from 'antd'
import { HistoryDetailPanel } from '../components/history/HistoryDetailPanel'
import { TravelHistorySidebar } from '../components/history/TravelHistorySidebar'
import type { HistoryPageData } from '../hooks/useHistoryPageData'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme } from '../utils/theme.tsx'
import { useI18n } from '../i18n'

const { Content } = Layout

type HistoryLayoutProps = HistoryPageData

export function HistoryLayout({
  histories,
  selectedHistory,
  selectedHistoryId,
  setSelectedHistoryId,
  isLoadingList,
  isLoadingDetail,
}: HistoryLayoutProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const { t } = useI18n()

  return (
    <Content className="h-[calc(100vh-72px)] overflow-hidden" style={{ background: colors.bg }}>
      <div className="flex h-full">
        <TravelHistorySidebar
          histories={histories}
          onSelectHistory={setSelectedHistoryId}
          selectedHistoryId={selectedHistoryId}
          isLoading={isLoadingList}
        />
        {selectedHistory ? (
          <HistoryDetailPanel history={selectedHistory} isLoadingDetail={isLoadingDetail} />
        ) : (
          <div
            className="flex min-w-0 flex-1 items-center justify-center text-[14px] text-slate-400 dark:text-slate-500"
            style={{ background: colors.bg }}
          >
            {isLoadingList ? t('history.loading') : t('history.empty')}
          </div>
        )}
      </div>
    </Content>
  )
}
