import type { Dispatch, SetStateAction } from 'react'
import { Empty, Layout } from 'antd'
import { ExpenseSummaryCard } from './ExpenseSummaryCard'
import { ItineraryPanel } from './ItineraryPanel'
import type { ExpenseCategory, ItineraryItem } from '../../types/chat'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { resolveTheme } from '../../utils/theme'
import { useI18n } from '../../i18n'

const { Sider } = Layout

type TripPlanSiderProps = {
  activeDate: string
  currentItems: ItineraryItem[]
  datesList: string[]
  expensesByCategory: ExpenseCategory[]
  isEmpty: boolean
  onSelectedDateIndexChange: Dispatch<SetStateAction<number>>
  pieConicGradient: string
  selectedDateIndex: number
  spentCny: number
}

export function TripPlanSider({
  activeDate,
  currentItems,
  datesList,
  expensesByCategory,
  isEmpty,
  onSelectedDateIndexChange,
  pieConicGradient,
  selectedDateIndex,
  spentCny,
}: TripPlanSiderProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const resolved = resolveTheme(theme)
  const { t } = useI18n()

  return (
    <Sider
      width={340}
      theme={resolved === 'dark' ? 'dark' : 'light'}
      className="border-l border-slate-200 bg-white overflow-y-auto dark:border-slate-700 dark:bg-slate-900"
    >
      {isEmpty ? (
        <div className="flex h-full items-center justify-center p-4">
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('chat.startPlanHint')} />
        </div>
      ) : (
        <div className="w-full space-y-2 p-4 pt-2">
          <ExpenseSummaryCard
            expensesByCategory={expensesByCategory}
            pieConicGradient={pieConicGradient}
            spentCny={spentCny}
          />
          <ItineraryPanel
            activeDate={activeDate}
            currentItems={currentItems}
            datesList={datesList}
            onSelectedDateIndexChange={onSelectedDateIndexChange}
            selectedDateIndex={selectedDateIndex}
          />
        </div>
      )}
    </Sider>
  )
}