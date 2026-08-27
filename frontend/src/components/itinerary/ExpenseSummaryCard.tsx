import { Card } from 'antd'
import type { ExpenseCategory } from '../../types/chat'
import { useI18n } from '../../i18n'

type ExpenseSummaryCardProps = {
  expensesByCategory: ExpenseCategory[]
  pieConicGradient: string
  spentCny: number
}

export function ExpenseSummaryCard({ expensesByCategory, pieConicGradient, spentCny }: ExpenseSummaryCardProps) {
  const { t } = useI18n()
  return (
    <Card className="rounded-2xl shadow-sm" styles={{ body: { padding: 14 } }} title={t('chat.expenseTitle')}>
      <div className="flex items-center gap-4 py-2">
        <div
          className="relative h-28 w-28 shrink-0 rounded-full shadow-inner flex items-center justify-center"
          style={{ background: pieConicGradient }}
        >
          <div className="h-16 w-16 rounded-full bg-white flex flex-col items-center justify-center shadow-sm dark:bg-slate-900">
            <span className="text-[10px] text-slate-400 dark:text-slate-500">{t('chat.used')}</span>
            <span className="text-[12px] font-bold text-slate-800 dark:text-slate-100">¥{spentCny}</span>
          </div>
        </div>

        <div className="flex-1 space-y-1.5 text-[12px]">
          {expensesByCategory.map((category) => (
            <div key={category.name} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: category.color }} />
                <span className="text-slate-600 dark:text-slate-300">{category.name}</span>
              </div>
              <span className="font-semibold text-slate-800 dark:text-slate-100">¥{category.amount}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
