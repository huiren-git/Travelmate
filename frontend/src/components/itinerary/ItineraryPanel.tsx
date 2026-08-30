import type { Dispatch, SetStateAction } from 'react'
import { Button, Card, List } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { ItineraryStatusTag } from '../common/StatusTags'
import { ItineraryImage } from '../common/ItineraryImage'
import type { ItineraryItem } from '../../types/chat'
import { useI18n } from '../../i18n'

type ItineraryPanelProps = {
  activeDate: string
  currentItems: ItineraryItem[]
  datesList: string[]
  onSelectedDateIndexChange: Dispatch<SetStateAction<number>>
  selectedDateIndex: number
}

export function ItineraryPanel({
  activeDate,
  currentItems,
  datesList,
  onSelectedDateIndexChange,
  selectedDateIndex,
}: ItineraryPanelProps) {
  const { t } = useI18n()
  return (
    <Card className="rounded-2xl shadow-sm" title={t('chat.itinerary')} styles={{ body: { padding: 12 } }}>
      <div className="mb-3 flex items-center justify-between border-b border-slate-100 pb-2 dark:border-slate-700">
        <Button
          type="text"
          size="small"
          icon={<LeftOutlined />}
          disabled={selectedDateIndex === 0}
          onClick={() => onSelectedDateIndexChange((previousIndex) => Math.max(0, previousIndex - 1))}
        />
        <div className="text-center font-semibold text-slate-800 text-[14px] dark:text-slate-100">
          Day {selectedDateIndex + 1} ({activeDate})
        </div>
        <Button
          type="text"
          size="small"
          icon={<RightOutlined />}
          disabled={selectedDateIndex === datesList.length - 1}
          onClick={() => onSelectedDateIndexChange((previousIndex) => Math.min(datesList.length - 1, previousIndex + 1))}
        />
      </div>

      <List
        dataSource={currentItems}
        split={false}
        renderItem={(item) => (
          <List.Item className="p-0 mb-3">
            <Card
              size="small"
              className="w-full overflow-hidden rounded-2xl shadow-sm bg-white ring-1 ring-slate-100 dark:bg-slate-800 dark:ring-slate-700"
              styles={{ body: { padding: 12 } }}
              cover={
                <ItineraryImage
                  src={item.imageUrl}
                  alt={item.attractionName}
                  category={item.category}
                  className="h-[110px] w-full object-cover"
                />
              }
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-semibold text-slate-900 dark:text-slate-100">{item.attractionName}</div>
                  <div className="mt-1 text-[12px] text-slate-500 dark:text-slate-400">
                    {item.timeRange}{item.duration ? ` · 预计 ${item.duration}` : ''}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[14px] font-semibold text-slate-900 dark:text-slate-100">{item.priceLabel ?? `¥${item.priceCny}`}</div>
                  <div className="mt-1">
                    <ItineraryStatusTag status={item.status} />
                  </div>
                </div>
              </div>
            </Card>
          </List.Item>
        )}
      />
    </Card>
  )
}
