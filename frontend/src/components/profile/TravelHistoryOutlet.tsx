import { Alert, Card, Empty, List, Skeleton, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { formatCurrencyCny } from '../../utils/historyFormat'
import { useI18n } from '../../i18n'

type TravelHistoryOutletProps = {
  histories: TravelHistory[]
  isLoading: boolean
  error: string | null
}

// 后端无行程级封面：优先 coverImageUrl，否则取首条行程图，再否则返回 null（渲染渐变占位）
function coverOf(history: TravelHistory): string | null {
  return history.coverImageUrl || history.routeItems?.[0]?.imageUrl || null
}

export function TravelHistoryOutlet({ histories, isLoading, error }: TravelHistoryOutletProps) {
  const { t } = useI18n()

  return (
    <Card
      className="flex h-full flex-col rounded-2xl border-0 shadow-sm"
      title={t('profile.travelHistory')}
      styles={{ body: { flex: 1, minHeight: 0, overflowY: 'auto', padding: 0 } }}
    >
      {isLoading ? (
        <div className="space-y-4 p-4">
          {Array.from({ length: 3 }).map((_, idx) => (
            <Skeleton key={idx} active avatar={{ shape: 'square' }} paragraph={{ rows: 1 }} />
          ))}
        </div>
      ) : error ? (
        <div className="p-4">
          <Alert type="error" showIcon message={t('preferences.loadFailed')} description={error} />
        </div>
      ) : histories.length === 0 ? (
        <div className="flex h-full items-center justify-center">
          <Empty description={t('preferences.noRecord')} />
        </div>
      ) : (
        <List
          dataSource={histories}
          renderItem={(history) => {
            const cover = coverOf(history)
            return (
              <List.Item className="!px-4 py-4">
                <List.Item.Meta
                  avatar={
                    cover ? (
                      <img src={cover} alt={history.title} className="h-16 w-24 rounded-lg object-cover" />
                    ) : (
                      <div className="h-16 w-24 rounded-lg bg-gradient-to-br from-sky-200 to-indigo-200" />
                    )
                  }
                  title={<span className="font-semibold text-slate-900 dark:text-slate-100">{history.title}</span>}
                  description={
                    <span className="flex flex-wrap items-center gap-2 text-[12px] text-slate-500 dark:text-slate-400">
                      <span>{history.destination}</span>
                      <span>{history.dateRange}</span>
                      <span>{history.people} 人</span>
                    </span>
                  }
                />
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <Tag className="m-0 rounded-full">{history.status}</Tag>
                  <span className="text-[13px] font-semibold text-slate-900 dark:text-slate-100">{formatCurrencyCny(history.totalExpenseCny)}</span>
                </div>
              </List.Item>
            )
          }}
        />
      )}
    </Card>
  )
}
