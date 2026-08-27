import { Collapse } from 'antd'
import { getNodeLabel } from '../../api/traces'
import type { LlmCallStatus } from '../../types/trace'
import type { LlmEventWithSpan } from '../../utils/traceTree'
import { formatDateTime, formatDuration, formatTokens } from '../../utils/traceFormat'
import { useI18n } from '../../i18n'
import { TraceStatusTag } from './TraceStatusTag'

type TraceLlmCallListProps = {
  calls: LlmEventWithSpan[]
}

function PromptBlock({ label, text, mono }: { label: string; text: string; mono?: boolean }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800">
      <div className="text-[11px] font-medium text-slate-400 dark:text-slate-500">{label}</div>
      <pre className={`m-0 mt-1 max-h-60 overflow-auto whitespace-pre-wrap break-words text-[12px] leading-relaxed text-slate-700 dark:text-slate-300 ${mono ? 'font-mono' : ''}`}>
        {text || '—'}
      </pre>
    </div>
  )
}

export function TraceLlmCallList({ calls }: TraceLlmCallListProps) {
  const { t } = useI18n()
  const STATUS_LABEL: Record<LlmCallStatus, string> = {
    success: t('traces.status.success'),
    error: t('traces.status.error'),
    timeout: t('traces.status.timeout'),
  }
  if (calls.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-[13px] text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500">
        {t('traces.llm.empty')}
      </div>
    )
  }

  return (
    <Collapse
      accordion
      className="traces-llm-collapse"
      items={calls.map((call) => ({
        key: String(call.id),
        label: (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]">
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.llm.call')}</span>
              <span className="font-mono font-semibold text-slate-900 dark:text-slate-100">#{call.id}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.llm.source')}</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{getNodeLabel(call.span_node_name)}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.llm.model')}</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{call.model_name}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.llm.duration')}</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{formatDuration(call.duration_ms)}</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.llm.token')}</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">
                {formatTokens(call.total_tokens)}
                <span className="ml-1 text-[11px] text-slate-400 dark:text-slate-500">
                  (↑{formatTokens(call.prompt_tokens)} / ↓{formatTokens(call.response_tokens)})
                </span>
              </span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="text-slate-400 dark:text-slate-500">{t('traces.llm.status')}</span>
              <TraceStatusTag status={call.status} />
            </span>
          </div>
        ),
        children: (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[12px] text-slate-500 dark:text-slate-400">
              <span>
                {t('traces.llm.requestTime')} <span className="font-mono text-slate-700 dark:text-slate-300">{formatDateTime(call.request_time)}</span>
              </span>
              <span>
                {t('traces.llm.status')} <span className="text-slate-700 dark:text-slate-300">{STATUS_LABEL[call.status]}</span>
              </span>
              <span>
                Span ID <span className="font-mono text-slate-700 dark:text-slate-300">{call.span_id}</span>
              </span>
            </div>

            {call.error ? (
              <div className="rounded-lg bg-rose-50 px-3 py-2 text-[12px] text-rose-600 dark:bg-rose-500/15 dark:text-rose-300">
                <span className="font-medium">{t('traces.llm.error')}：</span>
                {call.error}
              </div>
            ) : null}

            <PromptBlock label={t('traces.llm.prompt')} text={call.prompt_text} mono />
            <PromptBlock label={t('traces.llm.response')} text={call.response_text} mono />
          </div>
        ),
      }))}
    />
  )
}
