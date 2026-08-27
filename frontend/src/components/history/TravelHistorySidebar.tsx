import { Card, List, Spin, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { formatPeopleCount, getTravelStatusColor } from '../../utils/historyFormat'
import { useI18n } from '../../i18n'

type TravelHistorySidebarProps = {
  histories: TravelHistory[]
  onSelectHistory: (historyId: string) => void
  selectedHistoryId: string
  isLoading?: boolean
}

export function TravelHistorySidebar({ histories, onSelectHistory, selectedHistoryId, isLoading }: TravelHistorySidebarProps) {
  const { t } = useI18n()
  return (
    <aside className="h-full w-[320px] shrink-0 border-r border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
      <div className="flex h-full flex-col p-4">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <div className="text-[20px] font-bold text-slate-900 dark:text-slate-100">
              {t('history.sidebar.title')}
            </div>
            <div className="mt-1 text-[12px] text-slate-500 dark:text-slate-400">
              {t('history.sidebar.subtitle')}
            </div>
          </div>
          <Tag className="m-0 rounded-full border-0 bg-blue-50 px-3 py-1 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300">
            {t('history.sidebar.count', { n: histories.length })}
          </Tag>
        </div>

        {isLoading && histories.length === 0 ? (
          <div className="flex flex-1 items-center justify-center">
            <Spin tip={t('history.sidebar.loading')} />
          </div>
        ) : (
          <List
            className="overflow-y-auto"
            dataSource={histories}
            split={false}
            renderItem={(history) => {
              const active = history.id === selectedHistoryId

              return (
                <List.Item className="p-0 pb-3">
                  <button type="button" className="w-full text-left" onClick={() => onSelectHistory(history.id)}>
                    <Card
                      className={[
                        'w-full overflow-hidden rounded-xl border transition',
                        active
                          ? 'border-blue-200 bg-blue-50/70 shadow-sm dark:border-blue-500/40 dark:bg-blue-500/10'
                          : 'border-slate-100 bg-white hover:border-blue-100 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-blue-500/30',
                      ].join(' ')}
                      styles={{ body: { padding: 14 } }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-[16px] font-semibold text-slate-900 dark:text-slate-100">
                            {history.destination}
                          </div>
                          <div className="mt-2 text-[13px] text-slate-500 dark:text-slate-400">
                            {history.dateRange}
                          </div>
                        </div>
                        <Tag color={getTravelStatusColor(history.status)} className="m-0 shrink-0 rounded-full">
                          {history.status}
                        </Tag>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[12px] text-slate-500 dark:text-slate-400">
                        <span>{history.title}</span>
                        <span>{formatPeopleCount(history.people)}</span>
                      </div>
                    </Card>
                  </button>
                </List.Item>
              )
            }}
          />
        )}
      </div>
    </aside>
  )
}
