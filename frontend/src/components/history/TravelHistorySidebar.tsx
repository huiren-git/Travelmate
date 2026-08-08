import { Card, List, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { formatPeopleCount, getTravelStatusColor } from '../../utils/historyFormat'

type TravelHistorySidebarProps = {
  histories: TravelHistory[]
  onSelectHistory: (historyId: string) => void
  selectedHistoryId: string
}

export function TravelHistorySidebar({ histories, onSelectHistory, selectedHistoryId }: TravelHistorySidebarProps) {
  return (
    <aside className="h-full w-[320px] shrink-0 border-r border-slate-200 bg-white">
      <div className="flex h-full flex-col p-4">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <div className="text-[20px] font-bold text-slate-900">旅行历史</div>
            <div className="mt-1 text-[12px] text-slate-500">Travelmate 历史记录</div>
          </div>
          <Tag className="m-0 rounded-full border-0 bg-blue-50 px-3 py-1 text-blue-600">{histories.length} 条</Tag>
        </div>

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
                      active ? 'border-blue-200 bg-blue-50/70 shadow-sm' : 'border-slate-100 bg-white hover:border-blue-100',
                    ].join(' ')}
                    styles={{ body: { padding: 14 } }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-[16px] font-semibold text-slate-900">{history.destination}</div>
                        <div className="mt-2 text-[13px] text-slate-500">{history.dateRange}</div>
                      </div>
                      <Tag color={getTravelStatusColor(history.status)} className="m-0 shrink-0 rounded-full">
                        {history.status}
                      </Tag>
                    </div>
                    <div className="mt-3 flex items-center justify-between text-[12px] text-slate-500">
                      <span>{history.title}</span>
                      <span>{formatPeopleCount(history.people)}</span>
                    </div>
                  </Card>
                </button>
              </List.Item>
            )
          }}
        />
      </div>
    </aside>
  )
}
