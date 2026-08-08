import { Card, List, Tag } from 'antd'
import type { TravelHistory } from '../../types/history'
import { buildExpensePieGradient, buildLineChartPoints } from '../../utils/historyCharts'
import { formatCurrencyCny } from '../../utils/historyFormat'

type HistoryExpenseOutletProps = {
  history: TravelHistory
}

export function HistoryExpenseOutlet({ history }: HistoryExpenseOutletProps) {
  const linePoints = buildLineChartPoints(history.dailyExpenses)
  const pieGradient = buildExpensePieGradient(history.categoryExpenses)

  return (
    <div className="space-y-5">
      <Card className="rounded-2xl border-0 shadow-sm" title="每日消费折线图" styles={{ body: { padding: 16 } }}>
        {history.dailyExpenses.length > 0 ? (
          <svg className="h-[210px] w-full" viewBox="0 0 560 180" role="img" aria-label="每日消费折线图">
            <line x1="28" y1="152" x2="532" y2="152" stroke="#e2e8f0" />
            <line x1="28" y1="28" x2="28" y2="152" stroke="#e2e8f0" />
            <polyline points={linePoints} fill="none" stroke="#0071EB" strokeLinecap="round" strokeWidth="4" />
            {history.dailyExpenses.map((expense, index) => {
              const [x, y] = linePoints.split(' ')[index]?.split(',').map(Number) ?? [28, 152]

              return (
                <g key={expense.date}>
                  <circle cx={x} cy={y} r="6" fill="#FF6F61" />
                  <text x={x} y="172" textAnchor="middle" fontSize="12" fill="#64748b">
                    {expense.date}
                  </text>
                  <text x={x} y={Math.max(18, y - 12)} textAnchor="middle" fontSize="12" fill="#0f172a">
                    {expense.amountCny}
                  </text>
                </g>
              )
            })}
          </svg>
        ) : (
          <div className="py-12 text-center text-[13px] text-slate-500">暂无消费趋势数据</div>
        )}
      </Card>

      <Card className="rounded-2xl border-0 shadow-sm" title="消费分类饼图" styles={{ body: { padding: 16 } }}>
        {history.categoryExpenses.length > 0 ? (
          <div className="flex items-center gap-8">
            <div
              className="flex h-36 w-36 shrink-0 items-center justify-center rounded-full shadow-inner"
              style={{ background: pieGradient }}
            >
              <div className="flex h-20 w-20 flex-col items-center justify-center rounded-full bg-white shadow-sm">
                <span className="text-[11px] text-slate-400">总计</span>
                <span className="text-[14px] font-bold text-slate-900">{formatCurrencyCny(history.totalExpenseCny)}</span>
              </div>
            </div>

            <div className="grid flex-1 gap-2">
              {history.categoryExpenses.map((category) => (
                <div key={category.name} className="flex items-center justify-between text-[13px]">
                  <span className="flex items-center gap-2 text-slate-600">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: category.color }} />
                    {category.name}
                  </span>
                  <span className="font-semibold text-slate-900">{formatCurrencyCny(category.amountCny)}</span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="py-12 text-center text-[13px] text-slate-500">暂无分类消费数据</div>
        )}
      </Card>

      <Card className="rounded-2xl border-0 shadow-sm" title="消费明细列表" styles={{ body: { padding: 0 } }}>
        <List
          dataSource={history.expenseDetails}
          renderItem={(expense) => (
            <List.Item className="px-4">
              <List.Item.Meta
                title={<span className="font-semibold text-slate-900">{expense.title}</span>}
                description={
                  <span className="flex items-center gap-2 text-[12px] text-slate-500">
                    <span>{expense.date}</span>
                    <Tag className="m-0 rounded-full">{expense.category}</Tag>
                  </span>
                }
              />
              <div className="font-semibold text-slate-900">{formatCurrencyCny(expense.amountCny)}</div>
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}
