import { useEffect, useState } from 'react'
import { Button, Card, DatePicker, InputNumber, Modal, Space, Tag, message } from 'antd'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { adoptReference, fetchReferenceTrips, type ReferenceTrip } from '../api/reference'
import { createChatThreadId } from '../api/chat'

const tagColor = (tag: string) => ({ 历史人文: 'purple', 轻松: 'green', 中等预算: 'blue', 经济: 'cyan', 高预算: 'gold', 紧凑: 'volcano' }[tag] ?? 'geekblue')

export default function ReferenceTripsPage() {
  const [items, setItems] = useState<ReferenceTrip[]>([])
  const [selected, setSelected] = useState<ReferenceTrip>()
  const [date, setDate] = useState(dayjs())
  const [days, setDays] = useState(1)
  const [travelers, setTravelers] = useState(2)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => { fetchReferenceTrips().then(({ items }) => setItems(items)).catch(() => message.error('加载参考行程失败')) }, [])

  function adopt() {
    if (!selected) return
    setLoading(true)
    const threadId = createChatThreadId()
    adoptReference(selected.id, { thread_id: threadId, start_date: date.format('YYYY-MM-DD'), duration: days, travelers, destination: selected.destination }, event => {
      if (event.event === 'done') { sessionStorage.setItem('reference-adoption', JSON.stringify({ threadId, data: event.data })); navigate('/chat') }
      if (event.event === 'error') message.error('采纳失败')
    }).finally(() => setLoading(false))
  }

  return <div className="mx-auto max-w-5xl p-6"><h1 className="mb-6 text-3xl font-bold">参考行程</h1><div className="grid gap-4 md:grid-cols-2">
    {items.map(item => <Card key={item.id} styles={{ body: { padding: 22 } }}><div className="mb-4 flex items-start justify-between gap-3"><h2 className="m-0 text-xl font-semibold">{item.destination} · {item.duration}天 · {item.travelers ?? 2}人</h2><span className="shrink-0 text-lg font-bold text-amber-600">{item.score}分</span></div><Space wrap className="mb-3">{item.tags?.map(tag => <Tag key={tag} color={tagColor(tag)} className="m-0 rounded-full px-3 py-1">{tag}</Tag>)}</Space><p className="min-h-12 text-slate-600">{item.experience_tips}</p><Button type="primary" onClick={() => { setSelected(item); setDays(item.duration); setTravelers(item.travelers ?? 2) }}>使用此方案</Button></Card>)}
  </div><Modal open={!!selected} onCancel={() => setSelected(undefined)} onOk={adopt} confirmLoading={loading} title="采纳参考行程"><p>出发日期 <DatePicker value={date} onChange={value => setDate(value || dayjs())} /></p><p>天数 <InputNumber min={1} value={days} onChange={value => setDays(Number(value) || 1)} /></p><p>人数 <InputNumber min={1} value={travelers} onChange={value => setTravelers(Number(value) || 1)} /></p></Modal></div>
}
