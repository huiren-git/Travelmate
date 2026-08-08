import { Tag } from 'antd'
import type { ConversationStatus, ItineraryStatus } from '../../types/chat'

type ConversationStatusTagProps = {
  status: ConversationStatus
}

type ItineraryStatusTagProps = {
  status: ItineraryStatus
}

export function ConversationStatusTag({ status }: ConversationStatusTagProps) {
  if (status === '进行中') {
    return (
      <Tag color="processing" className="m-0 rounded-full border-0 bg-blue-50 text-blue-600 font-normal">
        进行中
      </Tag>
    )
  }

  return (
    <Tag color="default" className="m-0 rounded-full border-0 bg-slate-100 text-slate-500 font-normal">
      已完成
    </Tag>
  )
}

export function ItineraryStatusTag({ status }: ItineraryStatusTagProps) {
  if (status === '已确认') return <Tag color="blue">{status}</Tag>
  if (status === '已完成') return <Tag color="green">{status}</Tag>
  return <Tag color="gold">{status}</Tag>
}
