import { getNodeLabel, getSpanTypeLabel } from '../../api/traces'
import type { SpanStatus, SpanSummaryItem, SpanType } from '../../types/trace'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { getTravelmateTheme } from '../../utils/theme'
import { useI18n } from '../../i18n'

type TraceNodeTimingBarsProps = {
  spans: SpanSummaryItem[]
  /** 展示用的最大条宽（px），默认 160 */
  maxWidth?: number
}

const SPAN_TYPE_BADGE: Record<SpanType, string> = {
  llm: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300',
  io: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300',
  function: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300',
  workflow: 'bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300',
}

function formatDuration(ms: number | null | undefined) {
  if (ms == null || ms <= 0) return '0s'
  const seconds = ms / 1000
  if (seconds < 1) return `${ms}ms`
  return `${seconds.toFixed(1)}s`
}

export function TraceNodeTimingBars({ spans, maxWidth = 170 }: TraceNodeTimingBarsProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const { t } = useI18n()
  if (spans.length === 0) {
    return <div className="text-[12px] text-slate-400 dark:text-slate-500">{t('traces.timing.empty')}</div>
  }
  const maxDuration = Math.max(1, ...spans.map((span) => span.duration_ms ?? 0))
  const STATUS_BAR_COLOR: Record<SpanStatus, string> = {
    success: colors.primary,
    running: colors.primary2,
    error: '#f43f5e',
  }

  return (
    <div className="flex flex-col gap-1.5">
      {spans.map((span, index) => {
        const duration = span.duration_ms ?? 0
        const widthRatio = duration > 0 ? duration / maxDuration : 0
        const isRunning = span.status === 'running' && duration > 0
        const badgeClass = SPAN_TYPE_BADGE[span.span_type] ?? 'bg-slate-100 text-slate-500 dark:bg-slate-700/60 dark:text-slate-300'
        return (
          <div key={`${span.node_name}-${index}`} className="flex items-center gap-2 text-[12px]">
            <span className="w-20 shrink-0 truncate font-mono text-slate-500 dark:text-slate-400" title={span.node_name}>
              {getNodeLabel(span.node_name)}
            </span>
            <span className={`shrink-0 rounded px-1 py-0.5 text-[10px] font-medium ${badgeClass}`}>
              {getSpanTypeLabel(span.span_type)}
            </span>
            <div className="relative h-3 shrink-0" style={{ width: maxWidth }}>
              <div className="absolute inset-y-0 left-0 rounded-full bg-slate-100 dark:bg-slate-700" style={{ width: maxWidth }} />
              <div
                className={`absolute inset-y-0 left-0 rounded-full transition-all ${isRunning ? 'animate-pulse' : ''}`}
                style={{
                  width: Math.max(duration > 0 ? 4 : 0, widthRatio * maxWidth),
                  background: STATUS_BAR_COLOR[span.status],
                }}
              />
            </div>
            <span className="shrink-0 font-mono tabular-nums text-slate-600 dark:text-slate-300">{formatDuration(span.duration_ms)}</span>
          </div>
        )
      })}
    </div>
  )
}
