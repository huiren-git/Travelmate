import { Card } from 'antd'
import { CalendarOutlined, TeamOutlined } from '@ant-design/icons'
import { ConversationStatusTag } from '../common/StatusTags'
import type { ConversationStatus, TripSummary } from '../../types/chat'

type TripSummaryCardProps = {
  conversationStatus: ConversationStatus
  remaining: number
  trip: TripSummary
}

export function TripSummaryCard({ conversationStatus, remaining, trip }: TripSummaryCardProps) {
  return (
    <Card
      className="rounded-2xl shadow-sm"
      styles={{ body: { padding: 16 } }}
      title={
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <div className="text-[22px] font-bold text-slate-900 leading-tight">{trip.title}</div>
            <div className="mt-2 flex items-center gap-4 text-[13px] text-slate-600">
              <div className="flex items-center gap-1.5">
                <CalendarOutlined className="text-blue-500" />
                <span>{trip.dateRange}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <TeamOutlined className="text-blue-500" />
                <span>{trip.people} 人同行</span>
              </div>
            </div>
          </div>
          <ConversationStatusTag status={conversationStatus} />
        </div>
      }
    >
      <div className="flex items-center justify-around py-2 border-t border-slate-100 mt-1">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-blue-600">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 10h18M7 15h10m-7 4h4M5 21h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div>
            <div className="text-[12px] text-slate-400">总预算</div>
            <div className="text-[18px] font-bold text-slate-800">¥ {trip.budgetCny.toLocaleString()}</div>
          </div>
        </div>

        <div className="h-8 w-[1px] bg-slate-200" />

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-50 text-red-500">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
          </div>
          <div>
            <div className="text-[12px] text-slate-400">已花费</div>
            <div className="text-[18px] font-bold text-red-500">¥ {trip.spentCny.toLocaleString()}</div>
          </div>
        </div>

        <div className="h-8 w-[1px] bg-slate-200" />

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50 text-emerald-500">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <div>
            <div className="text-[12px] text-slate-400">剩余预算</div>
            <div className="text-[18px] font-bold text-emerald-500">¥ {remaining.toLocaleString()}</div>
          </div>
        </div>
      </div>
    </Card>
  )
}
