import { Card } from 'antd'
import type { ExpenseCategory } from '../../types/chat'

type ExpenseSummaryCardProps = {
  expensesByCategory: ExpenseCategory[]
  pieConicGradient: string
  spentCny: number
}

export function ExpenseSummaryCard({ expensesByCategory, pieConicGradient, spentCny }: ExpenseSummaryCardProps) {
  return (
    <Card className="rounded-2xl shadow-sm" styles={{ body: { padding: 14 } }} title="Expense Summary">
      <div className="flex items-center gap-4 py-2">
        <div
          className="relative h-28 w-28 shrink-0 rounded-full shadow-inner flex items-center justify-center"
          style={{ background: pieConicGradient }}
        >
          <div className="h-16 w-16 rounded-full bg-white flex flex-col items-center justify-center shadow-sm">
            <span className="text-[10px] text-slate-400">已用</span>
            <span className="text-[12px] font-bold text-slate-800">¥{spentCny}</span>
          </div>
        </div>

        <div className="flex-1 space-y-1.5 text-[12px]">
          {expensesByCategory.map((category) => (
            <div key={category.name} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: category.color }} />
                <span className="text-slate-600">{category.name}</span>
              </div>
              <span className="font-semibold text-slate-800">¥{category.amount}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
