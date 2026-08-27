import { Card, List, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { buildExpensePieGradient, buildLineChartPoints } from '../../utils/historyCharts'
import { formatCurrencyCny } from '../../utils/historyFormat'
import { useI18n } from '../../i18n'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { getTravelmateTheme } from '../../utils/theme'

type HistoryExpenseOutletProps = {
  history: TravelHistory
}

export function HistoryExpenseOutlet({ history }: HistoryExpenseOutletProps) {
  const { t } = useI18n()
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const linePoints = buildLineChartPoints(history.dailyExpenses)
  const pieGradient = buildExpensePieGradient(history.categoryExpenses)

  return (
    <div className="space-y-5">
      {/* 使用 Grid 布局让折线图和饼图在桌面端同行展示，移动端自动堆叠 */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* 1. 每日消费折线图 */}
        <Card
          className="flex flex-col justify-between rounded-2xl border-0 bg-white shadow-sm dark:bg-slate-800 dark:shadow-none"
          title={t('history.expense.lineChart')}
          styles={{ body: { padding: 16, flex: 1 } }}
        >
          {history.dailyExpenses.length > 0 ? (
            <svg className="h-[210px] w-full" viewBox="0 0 560 180" role="img" aria-label={t('history.expense.lineChart')}>
              <line x1="28" y1="152" x2="532" y2="152" stroke={colors.border} />
              <line x1="28" y1="28" x2="28" y2="152" stroke={colors.border} />
              <polyline points={linePoints} fill="none" stroke={colors.primary} strokeLinecap="round" strokeWidth="4" />
              {history.dailyExpenses.map((expense, index) => {
                const [x, y] = linePoints.split(' ')[index]?.split(',').map(Number) ?? [28, 152]

                return (
                  <g key={expense.date}>
                    <circle cx={x} cy={y} r="6" fill={colors.accent} />
                    <text x={x} y="172" textAnchor="middle" fontSize="12" fill={colors.textSecondary}>
                      {expense.date}
                    </text>
                    <text x={x} y={Math.max(18, y - 12)} textAnchor="middle" fontSize="12" fill={colors.textPrimary}>
                      {expense.amountCny}
                    </text>
                  </g>
                )
              })}
            </svg>
          ) : (
            <div className="py-12 text-center text-[13px] text-slate-500 dark:text-slate-400">
              {t('history.expense.noTrend')}
            </div>
          )}
        </Card>

        {/* 2. 消费分类饼图 */}
        <Card
          className="flex flex-col justify-between rounded-2xl border-0 bg-white shadow-sm dark:bg-slate-800 dark:shadow-none"
          title={t('history.expense.pieChart')}
          styles={{ body: { padding: 16, flex: 1 } }}
        >
          {history.categoryExpenses.length > 0 ? (
            <div className="flex h-full items-center gap-6">
              <div
                className="flex h-36 w-36 shrink-0 items-center justify-center rounded-full shadow-inner"
                style={{ background: pieGradient }}
              >
                <div className="flex h-20 w-20 flex-col items-center justify-center rounded-full bg-white shadow-sm dark:bg-slate-800">
                  <span className="text-[11px] text-slate-400 dark:text-slate-500">{t('history.expense.total')}</span>
                  <span className="text-[14px] font-bold text-slate-900 dark:text-slate-100">
                    {formatCurrencyCny(history.totalExpenseCny)}
                  </span>
                </div>
              </div>

              <div className="grid flex-1 gap-2">
                {history.categoryExpenses.map((category) => (
                  <div key={category.name} className="flex items-center justify-between text-[13px]">
                    <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: category.color }} />
                      {category.name}
                    </span>
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      {formatCurrencyCny(category.amountCny)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-[13px] text-slate-500 dark:text-slate-400">
              {t('history.expense.noCategory')}
            </div>
          )}
        </Card>
      </div>

      {/* 3. 消费明细列表 */}
      <Card
        className="rounded-2xl border-0 bg-white shadow-sm dark:bg-slate-800 dark:shadow-none"
        title={t('history.expense.detailList')}
        styles={{ body: { padding: 0 } }}
      >
        <List
          dataSource={history.expenseDetails}
          renderItem={(expense) => (
            <List.Item className="!px-4">
              <List.Item.Meta
                title={<span className="font-semibold text-slate-900 dark:text-slate-100">{expense.title}</span>}
                description={
                  <span className="flex items-center gap-2 text-[12px] text-slate-500 dark:text-slate-400">
                    <span>{expense.date}</span>
                    <Tag className="m-0 rounded-full">{expense.category}</Tag>
                  </span>
                }
              />
              <div className="font-semibold text-slate-900 dark:text-slate-100">
                {formatCurrencyCny(expense.amountCny)}
              </div>
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}
