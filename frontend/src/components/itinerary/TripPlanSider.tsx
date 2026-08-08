import type { Dispatch, SetStateAction } from 'react'
import { Layout } from 'antd'
import { ExpenseSummaryCard } from './ExpenseSummaryCard'
import { ItineraryPanel } from './ItineraryPanel'
import type { ExpenseCategory, ItineraryItem } from '../../types/chat'

const { Sider } = Layout

type TripPlanSiderProps = {
  activeDate: string
  currentItems: ItineraryItem[]
  datesList: string[]
  expensesByCategory: ExpenseCategory[]
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
  onSelectedDateIndexChange,
  pieConicGradient,
  selectedDateIndex,
  spentCny,
}: TripPlanSiderProps) {
  return (
    <Sider width={340} theme="light" className="border-l border-slate-200 overflow-y-auto">
      <div className="h-full p-4 space-y-4">
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
    </Sider>
  )
}
