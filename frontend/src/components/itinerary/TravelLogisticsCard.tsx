import { Button, Card, Divider, Tag } from 'antd'
import type { TravelLogistics } from '../../types/chat'

export function TravelLogisticsCard({ logistics, onConfirm }: { logistics?: TravelLogistics; onConfirm?: (key: string) => void }) {
  if (!logistics) return null
  return <Card size="small" title="交通与住宿" className="rounded-2xl shadow-sm">
    <div className="flex justify-between gap-2"><div><div className="font-semibold">全程住宿：{logistics.accommodation.mode === 'home' ? '住家里（不安排酒店）' : logistics.accommodation.area}</div>{logistics.accommodation.mode !== 'home' && <div className="mt-1 text-slate-500">{logistics.accommodation.nights} 晚 · {logistics.accommodation.rooms} 间 · 规则估算 ¥{logistics.accommodation.cost}</div>}</div>{logistics.accommodation.mode === 'home' ? <Tag color="blue">无需安排</Tag> : logistics.accommodation.status === 'confirmed' ? <Tag color="green">已确认</Tag> : <Button size="small" onClick={() => onConfirm?.('accommodation')}>确认方案</Button>}</div>
    <Divider className="my-3" />
    {logistics.intercityLegs.map((leg, index) => <div key={`${leg.kind}-${index}`} className="mb-2 flex justify-between gap-2"><span>{leg.origin ?? '待补充出发地'} → {leg.destination} · {leg.mode}</span><span>{leg.status === 'confirmed' ? <Tag color="green">已确认</Tag> : leg.status === 'pending' ? <Tag color="orange">未计入预算</Tag> : <Button size="small" onClick={() => onConfirm?.(`intercity:${leg.kind}`)}>确认 ¥{leg.cost}</Button>}</span></div>)}
    {logistics.localTransportLegs.length > 0 && <><Divider className="my-3" />{logistics.localTransportLegs.map((leg, index) => <div key={`${leg.date}-${index}`} className="mb-1 text-slate-600">{leg.date}：{leg.fromName} → {leg.toName} · {leg.mode} · ¥{leg.cost} <Tag>{leg.estimateSource === 'amap' ? `高德路线 ${leg.distanceKm ?? '-'}km / ${leg.durationMinutes ?? '-'}分钟` : '规则估算'}</Tag></div>)}</>}
  </Card>
}
