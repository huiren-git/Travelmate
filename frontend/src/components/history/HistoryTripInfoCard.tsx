import { Button, Card } from 'antd'
import { BarChartOutlined, EnvironmentOutlined, TeamOutlined, WalletOutlined } from '@ant-design/icons'
import type { HistoryOutletKey, TravelHistory } from '../../types/history'
import { formatCurrencyCny, formatPeopleCount } from '../../utils/historyFormat'

type HistoryTripInfoCardProps = {
  activeOutlet: HistoryOutletKey
  history: TravelHistory
  onOutletChange: (outlet: HistoryOutletKey) => void
}

export function HistoryTripInfoCard({ activeOutlet, history, onOutletChange }: HistoryTripInfoCardProps) {
  return (
    <Card className="rounded-2xl border-0 shadow-sm" styles={{ body: { padding: 18 } }}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="m-0 text-[28px] font-bold leading-tight text-slate-900">{history.title}</h1>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[12px] font-medium text-slate-600">
              {history.status}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-4 text-[14px] text-slate-500">
            <span>{history.destination}</span>
            <span>{history.dateRange}</span>
            <span className="flex items-center gap-1.5">
              <TeamOutlined className="text-blue-500" />
              {formatPeopleCount(history.people)}
            </span>
            <span className="flex items-center gap-1.5">
              <WalletOutlined className="text-blue-500" />
              {formatCurrencyCny(history.totalExpenseCny)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Button
            type={activeOutlet === 'route' ? 'primary' : 'default'}
            icon={<EnvironmentOutlined />}
            onClick={() => onOutletChange('route')}
          >
            行程轨迹
          </Button>
          <Button
            type={activeOutlet === 'expense' ? 'primary' : 'default'}
            icon={<BarChartOutlined />}
            onClick={() => onOutletChange('expense')}
          >
            支出统计
          </Button>
        </div>
      </div>
    </Card>
  )
}
