import { getNodeLabel, getSpanTypeLabel } from '../../api/traces'
import type { SpanDetailItem, SpanStatus, SpanType } from '../../types/trace'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { getTravelmateTheme } from '../../utils/theme'
import { formatDuration, formatTokens } from '../../utils/traceFormat'
import { flattenSpans, getSpanStartOffsetMs } from '../../utils/traceTree'
import { useI18n } from '../../i18n'

type TraceWaterfallProps = {
  spans: SpanDetailItem[]
  traceStartIso: string
  totalMs: number
}

const SPAN_TYPE_BADGE: Record<SpanType, string> = {
  llm: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300',
  io: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300',
  function: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300',
  workflow: 'bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300',
}

export function TraceWaterfall({ spans, traceStartIso, totalMs }: TraceWaterfallProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const { t } = useI18n()
  const span = Math.max(1, totalMs)
  const flat = flattenSpans(spans).filter((s) => (s.duration_ms ?? 0) > 0)
  const STATUS_BAR_COLOR: Record<SpanStatus, string> = {
    success: colors.primary,
    running: colors.primary2,
    error: '#f43f5e',
  }

  if (flat.length === 0) {
    return <div className="text-[13px] text-slate-400 dark:text-slate-500">{t('traces.timing.empty')}</div>
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[11px] text-slate-400 dark:text-slate-500">
        <span className="w-24 shrink-0">{t('traces.waterfall.node')}</span>
        <div className="relative h-4 flex-1">
          <span className="absolute left-0 top-0">0</span>
          <span className="absolute right-0 top-0 text-right">{formatDuration(span)}</span>
        </div>
        <span className="w-32 shrink-0 text-right">{t('traces.waterfall.metrics')}</span>
      </div>

      {flat.map((node, index) => {
        const duration = node.duration_ms ?? 0
        const startOffset = getSpanStartOffsetMs(traceStartIso, node.start_time)
        const leftPct = (startOffset / span) * 100
        const widthPct = Math.max((duration / span) * 100, 0.5)
        const isRunning = node.status === 'running'
        const badgeClass = SPAN_TYPE_BADGE[node.span_type] ?? 'bg-slate-100 text-slate-500 dark:bg-slate-700/60 dark:text-slate-300'
        // 估算 token：若有 llm_events 则汇总，否则显示 —
        const tokenSum = node.llm_events.reduce((sum, ev) => sum + ev.total_tokens, 0)
        return (
          <div key={`${node.span_id}-${index}`} className="flex items-center gap-2">
            <span className="w-24 shrink-0 truncate font-mono text-[12px] text-slate-500 dark:text-slate-400" title={node.node_name}>
              {getNodeLabel(node.node_name)}
            </span>
            <span className={`shrink-0 rounded px-1 py-0.5 text-[10px] font-medium ${badgeClass}`}>
              {getSpanTypeLabel(node.span_type)}
            </span>
            <div className="relative h-5 flex-1 rounded bg-slate-100 dark:bg-slate-700">
              <div
                className={`absolute inset-y-0.5 rounded transition-all ${isRunning ? 'animate-pulse' : ''}`}
                style={{ left: `${leftPct}%`, width: `${widthPct}%`, background: STATUS_BAR_COLOR[node.status] }}
              />
              <span
                className="absolute inset-y-0 flex items-center pl-2 text-[10px] font-medium text-white"
                style={{ left: `${leftPct}%` }}
              >
                {widthPct > 8 ? formatDuration(duration) : ''}
              </span>
            </div>
            <span className="w-32 shrink-0 text-right font-mono text-[11px] tabular-nums text-slate-600 dark:text-slate-300">
              {formatDuration(duration)} · {tokenSum > 0 ? formatTokens(tokenSum) : '—'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
