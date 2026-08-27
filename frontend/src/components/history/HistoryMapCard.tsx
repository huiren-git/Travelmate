import { Card, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { useI18n } from '../../i18n'

type HistoryMapCardProps = {
  history: TravelHistory
}

export function HistoryMapCard({ history }: HistoryMapCardProps) {
  const { t } = useI18n()
  return (
    <Card
      className="rounded-2xl border-0 bg-white shadow-sm dark:bg-slate-800 dark:shadow-none"
      styles={{ body: { padding: 16 } }}
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="text-[13px] font-semibold text-blue-700 dark:text-blue-400">
            {t('history.map.title')}
          </div>
          <div className="mt-1 text-[24px] font-bold text-slate-900 dark:text-slate-100">
            {history.title}
          </div>
        </div>
        <Tag className="m-0 rounded-full border-0 bg-blue-50 px-3 py-1 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300">
          {t('history.map.nodes', { n: history.routeItems.length })}
        </Tag>
      </div>

      <div className="relative h-[260px] overflow-hidden rounded-xl bg-blue-50 dark:bg-slate-900/60">
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(27,140,209,0.12)_1px,transparent_1px),linear-gradient(rgba(27,140,209,0.12)_1px,transparent_1px)] bg-[size:36px_36px]" />
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 640 260" aria-hidden="true">
          <path
            d="M70 190 C160 80 245 210 330 118 S520 70 570 166"
            fill="none"
            stroke="#0071EB"
            strokeDasharray="10 8"
            strokeLinecap="round"
            strokeWidth="4"
          />
          {[
            [70, 190],
            [210, 128],
            [360, 116],
            [570, 166],
          ].map(([x, y], index) => (
            <g key={`${x}-${y}`}>
              <circle cx={x} cy={y} r="13" fill="#FF6F61" />
              <text x={x} y={y + 4} textAnchor="middle" fontSize="12" fontWeight="700" fill="#ffffff">
                {index + 1}
              </text>
            </g>
          ))}
        </svg>
        <div className="absolute left-5 top-5">
          <div className="text-[13px] font-semibold text-blue-700 dark:text-blue-400">
            {t('history.map.visualization')}
          </div>
          <div className="mt-1 text-[14px] text-slate-600 dark:text-slate-300">
            {history.dateRange}
          </div>
        </div>
      </div>
    </Card>
  )
}
