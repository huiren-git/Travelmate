import { Card, List, Tag } from 'antd'
import { travelHistories } from '../../store/historyData'
import { formatCurrencyCny } from '../../utils/historyFormat'

export function TravelHistoryOutlet() {
  return (
    <Card className="rounded-2xl border-0 shadow-sm" title="旅行历史" styles={{ body: { padding: 0 } }}>
      <List
        dataSource={travelHistories}
        renderItem={(history) => (
          <List.Item className="px-5 py-4">
            <List.Item.Meta
              avatar={<img src={history.coverImageUrl} alt={history.title} className="h-16 w-24 rounded-lg object-cover" />}
              title={<span className="font-semibold text-slate-900">{history.title}</span>}
              description={
                <span className="flex flex-wrap items-center gap-2 text-[12px] text-slate-500">
                  <span>{history.destination}</span>
                  <span>{history.dateRange}</span>
                  <span>{history.people} 人出行</span>
                </span>
              }
            />
            <div className="flex shrink-0 flex-col items-end gap-2">
              <Tag className="m-0 rounded-full">{history.status}</Tag>
              <span className="text-[13px] font-semibold text-slate-900">{formatCurrencyCny(history.totalExpenseCny)}</span>
            </div>
          </List.Item>
        )}
      />
    </Card>
  )
}
