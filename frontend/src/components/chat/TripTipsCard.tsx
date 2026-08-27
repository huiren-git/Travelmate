import { useState } from 'react'
import { Card } from 'antd'
import { CaretDownOutlined, CaretRightOutlined } from '@ant-design/icons'
import type { ItineraryItem } from '../../types/chat'
import { useI18n } from '../../i18n'

type TripTipsCardProps = {
  itinerary: ItineraryItem[]
}

type TipsGroup = {
  date: string
  items: ItineraryItem[]
}

export function TripTipsCard({ itinerary }: TripTipsCardProps) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(false)

  const tipsItems = itinerary.filter((item) => item.tips && item.tips.trim())
  if (tipsItems.length === 0) {
    return null
  }

  const groups: TipsGroup[] = []
  for (const item of tipsItems) {
    const existing = groups.find((group) => group.date === item.date)
    if (existing) {
      existing.items.push(item)
    } else {
      groups.push({ date: item.date, items: [item] })
    }
  }

  return (
    <Card className="!ml-12 !w-[80%] rounded-2xl shadow-sm" styles={{ body: { padding: 12 } }}>
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="flex w-full items-center justify-between text-left"
        >
          <span className="text-[14px] font-semibold text-slate-800 dark:text-slate-100">
            {t('chat.tripTips')}（{tipsItems.length}）
          </span>
          {expanded ? (
            <CaretDownOutlined className="text-slate-400 dark:text-slate-500" />
          ) : (
            <CaretRightOutlined className="text-slate-400 dark:text-slate-500" />
          )}
        </button>

        {expanded && (
          <div className="mt-3 space-y-3">
            {groups.map((group) => (
              <div key={group.date}>
                <div className="text-[12px] font-medium text-slate-400 dark:text-slate-500">{group.date}</div>
                <ul className="mt-1 space-y-1.5">
                  {group.items.map((item, index) => (
                    <li key={`${group.date}-${index}`} className="flex gap-2 text-[13px] leading-snug">
                      <span className="shrink-0 font-medium text-slate-900 dark:text-slate-100">{item.attractionName}</span>
                      <span className="text-slate-500 dark:text-slate-400">{item.tips}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
    </Card>
  )
}
