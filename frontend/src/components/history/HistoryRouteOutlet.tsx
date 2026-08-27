import { Card, Timeline } from 'antd'
import { CheckCircleFilled, DownOutlined } from '@ant-design/icons'
import type { TravelHistory } from '../../types/history'
import { formatCurrencyCny } from '../../utils/historyFormat'
import { ItineraryImage } from '../common/ItineraryImage'
import { useI18n } from '../../i18n'

type HistoryRouteOutletProps = {
  history: TravelHistory
}

export function HistoryRouteOutlet({ history }: HistoryRouteOutletProps) {
  const { t } = useI18n()
  // 生成行程节点列表
  const routeTimelineItems = history.routeItems.map((item) => ({
    dot: (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-[#0071EB]/10 text-[#0071EB] dark:bg-[#3B9EFF]/15 dark:text-[#7CC0FF]">
        <DownOutlined className="text-[10px]" />
      </div>
    ),
    children: (
      <div className="flex items-center gap-4">
        <div className="whitespace-nowrap pt-0.5 text-[13px] font-semibold text-[#0071EB] dark:text-[#7CC0FF]">
          {item.time}
        </div>
        <Card
          className="flex-1 rounded-xl border-slate-100 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:shadow-none"
          styles={{ body: { padding: 12 } }}
        >
          <div className="flex gap-3">
            <ItineraryImage
              src={item.imageUrl}
              alt={item.attractionName}
              className="h-[92px] w-[128px] shrink-0 rounded-lg object-cover"
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[16px] font-semibold text-slate-900 dark:text-slate-100">
                    {item.attractionName}
                  </div>
                </div>
                <div className="shrink-0 text-[14px] font-semibold text-[#FF6F61] dark:text-[#FF8A7A]">
                  {formatCurrencyCny(item.costCny)}
                </div>
              </div>
              <p className="m-0 mt-2 text-[13px] leading-relaxed text-slate-600 dark:text-slate-300">
                {item.description}
              </p>
            </div>
          </div>
        </Card>
      </div>
    ),
  }))

  // 追加 End 终点节点
  const endItem = {
    dot: (
      <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400">
        <CheckCircleFilled className="text-[12px]" />
      </div>
    ),
    children: (
      <div className="flex items-center gap-2 py-0.5 text-[13px] font-semibold text-emerald-600 dark:text-emerald-400">
        <span>{t('history.route.end')}</span>
      </div>
    ),
  }

  return (
    <Card
      className="rounded-2xl border-0 bg-white shadow-sm dark:bg-slate-800 dark:shadow-none"
      title={t('history.route.title')}
      styles={{ body: { padding: 0 } }}
    >
      <Timeline className="!px-6 !py-6" items={[...routeTimelineItems, endItem]} />
    </Card>
  )
}
