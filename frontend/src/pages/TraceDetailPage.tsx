import { ArrowLeftOutlined } from '@ant-design/icons'
import { Layout, Skeleton } from 'antd'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchTraceDetail } from '../api/traces'
import { TraceLlmCallList } from '../components/traces/TraceLlmCallList'
import { TraceSpanList } from '../components/traces/TraceSpanList'
import { TraceStatusTag } from '../components/traces/TraceStatusTag'
import { TraceWaterfall } from '../components/traces/TraceWaterfall'
import type { TraceDetailData } from '../types/trace'
import { formatDateTime, formatDuration, formatTokens } from '../utils/traceFormat'
import { collectLlmEvents, computeTraceDurationMs } from '../utils/traceTree'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme } from '../utils/theme.tsx'
import { useI18n } from '../i18n'

const { Content } = Layout

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="m-0 text-[16px] font-semibold text-slate-900 dark:text-slate-100">{children}</h2>
}

function SummaryRow({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[13px]">{children}</div>
}

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="text-slate-400 dark:text-slate-500">{label}</span>
      <span className={`text-slate-700 dark:text-slate-200 ${mono ? 'font-mono' : ''}`}>{value}</span>
    </span>
  )
}

export default function TraceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const { t } = useI18n()
  const [detail, setDetail] = useState<TraceDetailData | undefined>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    let active = true
    if (!id) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(undefined)
    fetchTraceDetail(id)
      .then((data) => {
        if (!active) return
        setDetail(data)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(err instanceof Error ? err.message : '加载 Trace 详情失败')
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [id])

  const trace = detail?.trace
  const spans = detail?.spans ?? []
  const durationMs = trace ? computeTraceDurationMs(trace, spans) : 0
  const llmEvents = trace ? collectLlmEvents(spans) : []

  return (
    <Content className="h-[calc(100vh-72px)] overflow-auto" style={{ background: colors.bg }}>
      <div className="mx-auto max-w-[1040px] px-6 py-6">
        <Link to="/traces" className="inline-flex items-center gap-1 text-[13px] text-slate-500 transition-colors hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200">
          <ArrowLeftOutlined /> {t('trace.back')}
        </Link>

        {loading ? (
          <div className="mt-4">
            <Skeleton active paragraph={{ rows: 8 }} />
          </div>
        ) : error ? (
          <div className="mt-10 rounded-xl border border-rose-200 bg-rose-50 p-10 text-center text-[14px] text-rose-600 dark:border-rose-900 dark:bg-rose-950/40">
            {error}
          </div>
        ) : !detail || !trace ? (
          <div className="mt-10 rounded-xl border border-slate-200 bg-white p-10 text-center text-[14px] text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            未找到 Trace：<span className="font-mono">{id}</span>
          </div>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            {/* 顶部：Trace 元信息 */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between gap-2">
                <SectionTitle>Trace 详情</SectionTitle>
                <Link to="/traces" className="text-[12px] text-blue-600 hover:text-blue-700 dark:text-blue-400">
                  /traces
                </Link>
              </div>

              <div className="mt-4 flex flex-col gap-2">
                <SummaryRow>
                  <Field label="Trace ID:" value={trace.trace_id} mono />
                  <Field label="状态:" value={<TraceStatusTag status={trace.status} />} />
                  <Field label="耗时:" value={formatDuration(durationMs)} mono />
                  <Field label="Token:" value={formatTokens(trace.total_tokens)} mono />
                </SummaryRow>

                <SummaryRow>
                  <Field label="用户:" value={trace.user_id} mono />
                  <Field label="会话:" value={trace.thread_id} mono />
                </SummaryRow>

                <SummaryRow>
                  <Field label="开始时间:" value={formatDateTime(trace.start_time)} mono />
                  <Field label="结束时间:" value={formatDateTime(trace.end_time)} mono />
                </SummaryRow>

                <div className="flex items-start gap-1.5">
                  <span className="shrink-0 text-slate-400 dark:text-slate-500">用户输入:</span>
                  <span className="text-slate-700 dark:text-slate-200">{trace.input_message || '—'}</span>
                </div>

                {trace.error_message ? (
                  <div className="mt-1 rounded-lg bg-rose-50 px-3 py-2 text-[12px] text-rose-600 dark:bg-rose-950/40">
                    <span className="font-medium">错误信息：</span>
                    {trace.error_message}
                  </div>
                ) : null}
              </div>
            </div>

            {/* 瀑布图：各节点耗时与 Token */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <SectionTitle>瀑布图</SectionTitle>
              <div className="mt-4">
                <TraceWaterfall spans={spans} traceStartIso={trace.start_time} totalMs={durationMs} />
              </div>
            </div>

            {/* Span 详情（树形） */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <SectionTitle>Span 详情</SectionTitle>
              <div className="mt-4">
                <TraceSpanList spans={spans} />
              </div>
            </div>

            {/* LLM 调用详情 */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center justify-between">
                <SectionTitle>LLM 调用详情</SectionTitle>
                <span className="text-[12px] text-slate-400 dark:text-slate-500">共 {llmEvents.length} 次调用</span>
              </div>
              <div className="mt-4">
                <TraceLlmCallList calls={llmEvents} />
              </div>
            </div>
          </div>
        )}
      </div>
    </Content>
  )
}
