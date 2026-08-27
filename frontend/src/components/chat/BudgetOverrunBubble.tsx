import { useState } from 'react'
import { Avatar } from 'antd'
import type { BudgetInterruptPayload } from '../../api/chat'

type BudgetOverrunBubbleProps = {
  payload: BudgetInterruptPayload
  primaryColor: string
  onResolve: (action: 'accept' | 'modify', hint?: string) => void
  isResolving: boolean
}

// 预算超支确认「气泡」（非弹窗）：以 assistant 气泡样式呈现提示 + 操作按钮，挂在对话流中。
export function BudgetOverrunBubble({ payload, primaryColor, onResolve, isResolving }: BudgetOverrunBubbleProps) {
  const [adjusting, setAdjusting] = useState(false)
  const [hint, setHint] = useState('')

  return (
    <div className="flex gap-3 justify-start">
      <Avatar size={36} className="text-white shrink-0 shadow-sm" style={{ background: primaryColor }}>
        T
      </Avatar>
      <div className="max-w-[80%] rounded-2xl px-4 py-3 shadow-sm bg-white text-slate-800 ring-1 ring-slate-100 dark:bg-slate-800 dark:text-slate-100 dark:ring-slate-700">
        <div className="whitespace-pre-wrap text-[14px] leading-relaxed">
          {payload.description ?? '行程预算超出您的上限，请确认如何处理。'}
        </div>

        {!adjusting ? (
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={isResolving}
              onClick={() => onResolve('accept')}
              className="rounded-lg px-3 py-1.5 text-[13px] font-medium text-white disabled:opacity-60"
              style={{ background: primaryColor }}
            >
              接受超支，继续
            </button>
            <button
              type="button"
              disabled={isResolving}
              onClick={() => setAdjusting(true)}
              className="rounded-lg px-3 py-1.5 text-[13px] font-medium ring-1 ring-slate-200 text-slate-700 disabled:opacity-60 dark:ring-slate-600 dark:text-slate-200"
            >
              调整预算或行程
            </button>
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            <textarea
              value={hint}
              disabled={isResolving}
              onChange={(e) => setHint(e.target.value)}
              rows={2}
              placeholder="请输入调整要求，例如：把预算提高到 500 元，或削减一个最贵的景点"
              className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-[13px] text-slate-700 outline-none focus:border-slate-400 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
            />
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={isResolving || !hint.trim()}
                onClick={() => onResolve('modify', hint.trim() || undefined)}
                className="rounded-lg px-3 py-1.5 text-[13px] font-medium text-white disabled:opacity-60"
                style={{ background: primaryColor }}
              >
                提交调整
              </button>
              <button
                type="button"
                disabled={isResolving}
                onClick={() => setAdjusting(false)}
                className="rounded-lg px-3 py-1.5 text-[13px] font-medium ring-1 ring-slate-200 text-slate-700 dark:ring-slate-600 dark:text-slate-200"
              >
                返回
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
