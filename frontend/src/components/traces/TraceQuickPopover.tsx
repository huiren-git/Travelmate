import { Skeleton } from 'antd'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchTraceSummary } from '../../api/traces'
import type { TraceSummaryData } from '../../types/trace'
import { formatDuration, formatTokens } from '../../utils/traceFormat'
import { useI18n } from '../../i18n'
import { TraceNodeTimingBars } from './TraceNodeTimingBars'
import { TraceStatusTag } from './TraceStatusTag'

type TraceQuickPopoverContentProps = {
  traceId: string
}

export function TraceQuickPopoverContent({ traceId }: TraceQuickPopoverContentProps) {
  const [summary, setSummary] = useState<TraceSummaryData | undefined>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | undefined>()
  const { t } = useI18n()

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(undefined)
    fetchTraceSummary(traceId)
      .then((data) => {
        if (!active) return
        setSummary(data)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(err instanceof Error ? err.message : t('traces.quick.loadFailed'))
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [traceId, t])

  return (
    <div className="w-[320px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold text-slate-900 dark:text-slate-100">{t('traces.quick.title')}</span>
        {summary ? <TraceStatusTag status={summary.status} /> : null}
      </div>

      <div className="mt-1 truncate font-mono text-[11px] text-slate-500 dark:text-slate-400" title={traceId}>
        {traceId}
      </div>

      {loading ? (
        <div className="mt-3">
          <Skeleton active paragraph={{ rows: 4 }} />
        </div>
      ) : error ? (
        <div className="mt-3 rounded-md bg-rose-50 px-3 py-2 text-[12px] text-rose-600 dark:bg-rose-500/15 dark:text-rose-300">{error}</div>
      ) : summary ? (
        <>
          {/* 概览指标：总耗时 / Token / LLM 调用次数 */}
          <div className="mt-3 grid grid-cols-3 gap-2">
            <Metric label={t('traces.quick.totalDuration')} value={formatDuration(summary.total_duration_ms)} />
            <Metric label={t('traces.quick.token')} value={formatTokens(summary.total_tokens)} />
            <Metric label={t('traces.quick.llmCalls')} value={String(summary.llm_call_count)} />
          </div>

          {/* Span 列表：node_name / duration_ms / status / span_type */}
          <div className="mt-3 text-[12px] font-medium text-slate-700 dark:text-slate-300">
            {t('traces.quick.spanNodes', { n: summary.spans.length })}
          </div>
          <div className="mt-1.5">
            <TraceNodeTimingBars spans={summary.spans} maxWidth={180} />
          </div>
        </>
      ) : null}

      <div className="mt-3 border-t border-slate-100 pt-2 dark:border-slate-700">
        <Link
          to={`/traces/${traceId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
        >
          {t('traces.quick.fullDetail')} -&gt;
        </Link>
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-2 py-1.5 text-center dark:bg-slate-800">
      <div className="text-[10px] text-slate-400 dark:text-slate-500">{label}</div>
      <div className="mt-0.5 font-mono text-[13px] font-semibold text-slate-900 dark:text-slate-100">{value}</div>
    </div>
  )
}
