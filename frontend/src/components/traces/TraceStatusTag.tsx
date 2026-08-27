import { Tag } from 'antd'
import { useI18n } from '../../i18n'

/** 所有可能的状态枚举（Trace + Span + LLM 调用） */
export type TraceStatusKind = 'success' | 'error' | 'running' | 'cancelled' | 'timeout'

type TraceStatusTagProps = {
  status: TraceStatusKind
}

const STATUS_CLASS: Record<TraceStatusKind, string> = {
  success: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300',
  error: 'bg-rose-50 text-rose-600 dark:bg-rose-500/15 dark:text-rose-300',
  running: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300',
  cancelled: 'bg-slate-100 text-slate-500 dark:bg-slate-700/60 dark:text-slate-300',
  timeout: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300',
}

export function TraceStatusTag({ status }: TraceStatusTagProps) {
  const { t } = useI18n()
  const className = STATUS_CLASS[status] ?? STATUS_CLASS.error
  const label = t(`traces.status.${status}`)
  return (
    <Tag className={`m-0 rounded-full border-0 px-2 py-0.5 text-[12px] font-normal ${className}`}>{label}</Tag>
  )
}
