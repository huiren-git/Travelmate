import { Card, Timeline } from 'antd'
import type { TravelHistory } from '../../types/history'
import { formatCurrencyCny } from '../../utils/historyFormat'

type HistoryRouteOutletProps = {
  history: TravelHistory
}

export function HistoryRouteOutlet({ history }: HistoryRouteOutletProps) {
  return (
    <Card className="rounded-2xl border-0 shadow-sm" title="行程轨迹" styles={{ body: { padding: 0 } }}>
      <Timeline
        className="px-6 py-5"
        items={history.routeItems.map((item) => ({
          color: '#0071EB',
          children: (
            <Card className="mb-4 rounded-xl border-slate-100 shadow-sm" styles={{ body: { padding: 12 } }}>
              <div className="flex gap-3">
                <img
                  src={item.imageUrl}
                  alt={item.attractionName}
                  className="h-[92px] w-[128px] shrink-0 rounded-lg object-cover"
                  loading="lazy"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-[16px] font-semibold text-slate-900">{item.attractionName}</div>
                      <div className="mt-1 text-[12px] text-slate-500">{item.time}</div>
                    </div>
                    <div className="shrink-0 text-[14px] font-semibold text-[#FF6F61]">
                      {formatCurrencyCny(item.costCny)}
                    </div>
                  </div>
                  <p className="m-0 mt-3 text-[13px] leading-relaxed text-slate-600">{item.description}</p>
                </div>
              </div>
            </Card>
          ),
        }))}
      />
    </Card>
  )
}
