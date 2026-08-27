import { getNodeLabel, getSpanTypeLabel } from '../../api/traces'
import type { SpanDetailItem, SpanStatus, SpanType } from '../../types/trace'
import { formatDateTime, formatDuration } from '../../utils/traceFormat'
import { useI18n } from '../../i18n'
import { TraceStatusTag } from './TraceStatusTag'

type TraceSpanListProps = {
  spans: SpanDetailItem[]
}

const SPAN_TYPE_BADGE: Record<SpanType, string> = {
  llm: 'bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300',
  io: 'bg-amber-50 text-amber-600 dark:bg-amber-500/15 dark:text-amber-300',
  function: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300',
  workflow: 'bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300',
}

function tryFormatJson(text: string | null): string {
  if (!text) return '—'
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

function SpanCard({ span, depth, index }: { span: SpanDetailItem; depth: number; index: number }) {
  const { t } = useI18n()
  const badgeClass = SPAN_TYPE_BADGE[span.span_type] ?? 'bg-slate-100 text-slate-500 dark:bg-slate-700/60 dark:text-slate-300'
  const llmCount = span.llm_events?.length ?? 0

  return (
    <>
      <div
        className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
        style={{ marginLeft: depth * 20 }}
      >
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]">
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.index')}</span>
            <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">#{index}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.node')}</span>
            <span className="font-mono text-slate-700 dark:text-slate-300">{getNodeLabel(span.node_name)}</span>
            <span className="font-mono text-[11px] text-slate-400 dark:text-slate-500">({span.node_name})</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.type')}</span>
            <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${badgeClass}`}>
              {getSpanTypeLabel(span.span_type)}
            </span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.status')}</span>
            <TraceStatusTag status={span.status as SpanStatus} />
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.duration')}</span>
            <span className="font-mono text-slate-700 dark:text-slate-300">{formatDuration(span.duration_ms)}</span>
          </span>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px]">
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.spanId')}</span>
            <span className="font-mono text-slate-600 dark:text-slate-400" title={span.span_id}>
              {span.span_id}
            </span>
          </span>
          {span.parent_span_id ? (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.span.parentSpan')}</span>
              <span className="font-mono text-slate-600 dark:text-slate-400" title={span.parent_span_id}>
                {span.parent_span_id}
              </span>
            </span>
          ) : null}
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.start')}</span>
            <span className="font-mono text-slate-600 dark:text-slate-400">{formatDateTime(span.start_time)}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="text-slate-400 dark:text-slate-500">{t('traces.span.end')}</span>
            <span className="font-mono text-slate-600 dark:text-slate-400">{formatDateTime(span.end_time)}</span>
          </span>
          {llmCount > 0 ? (
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.span.llmCalls')}</span>
              <span className="font-mono text-blue-600 dark:text-blue-400">{llmCount} 次</span>
            </span>
          ) : null}
        </div>

        <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800">
          <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500">{t('traces.span.output')}</div>
          <pre className="m-0 mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-slate-700 dark:text-slate-300">
            {tryFormatJson(span.output_snapshot)}
          </pre>
        </div>
      </div>

      {span.children?.length ? (
        <div className="mt-2 flex flex-col gap-2 border-l-2 border-slate-100 pl-3 dark:border-slate-700">
          {span.children.map((child, i) => (
            <SpanCard key={`${child.span_id}-${i}`} span={child} depth={1} index={i + 1} />
          ))}
        </div>
      ) : null}
    </>
  )
}

export function TraceSpanList({ spans }: TraceSpanListProps) {
  const { t } = useI18n()
  if (spans.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-[13px] text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500">
        {t('traces.timing.empty')}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {spans.map((span, index) => (
        <SpanCard key={`${span.span_id}-${index}`} span={span} depth={0} index={index + 1} />
      ))}
    </div>
  )
}
