import { Button, Input, Select } from 'antd'
import type { TraceFilters, TraceStatus } from '../../types/trace'
import { useI18n } from '../../i18n'

type TraceFiltersBarProps = {
  filters: TraceFilters
  onChange: (patch: Partial<TraceFilters>) => void
  onSearch: () => void
  onReset: () => void
  loading?: boolean
}

const STATUS_OPTIONS: Array<{ label: string; value: TraceStatus | 'all' }> = [
  { label: 'all', value: 'all' },
  { label: 'success', value: 'success' },
  { label: 'error', value: 'error' },
  { label: 'running', value: 'running' },
  { label: 'cancelled', value: 'cancelled' },
]

const inputClass =
  'h-8 w-[180px] rounded-lg border border-slate-200 bg-white px-2 text-[13px] text-slate-700 outline-none transition-colors focus:border-blue-400 focus:ring-1 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

export function TraceFiltersBar({ filters, onChange, onSearch, onReset, loading }: TraceFiltersBarProps) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col items-left justify-between gap-3 border-b border-slate-200 bg-white px-5 py-3 dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center gap-2">
        <h1 className="m-0 text-[30px] font-semibold text-slate-900 dark:text-slate-100">{t('traces.title')}</h1>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 text-[12px] text-slate-500 dark:text-slate-400">
          <span>{t('traces.filters.startTime')}</span>
          <input
            type="datetime-local"
            value={filters.start_time ?? ''}
            onChange={(event) => onChange({ start_time: event.target.value || undefined })}
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-1 text-[12px] text-slate-500 dark:text-slate-400">
          <span>{t('traces.filters.endTime')}</span>
          <input
            type="datetime-local"
            value={filters.end_time ?? ''}
            onChange={(event) => onChange({ end_time: event.target.value || undefined })}
            className={inputClass}
          />
        </label>

        <label className="flex items-center gap-1 text-[12px] text-slate-500 dark:text-slate-400">
          <span>{t('traces.filters.userId')}:</span>
          <Input
            allowClear
            placeholder={t('traces.filters.userIdPlaceholder')}
            value={filters.user_id ?? ''}
            onChange={(event) => onChange({ user_id: event.target.value })}
            onPressEnter={onSearch}
            className="!w-[200px]"
            size="middle"
          />
        </label>

        <label className="flex items-center gap-1 text-[12px] text-slate-500 dark:text-slate-400">
          <span>{t('traces.filters.threadId')}:</span>
          <Input
            allowClear
            placeholder={t('traces.filters.threadIdPlaceholder')}
            value={filters.thread_id ?? ''}
            onChange={(event) => onChange({ thread_id: event.target.value })}
            onPressEnter={onSearch}
            className="!w-[200px]"
            size="middle"
          />
        </label>

        <label className="flex items-center gap-1 text-[12px] text-slate-500 dark:text-slate-400">
          <span>{t('traces.filters.status')}:</span>
          <Select
            value={filters.status ?? 'all'}
            onChange={(value) => onChange({ status: value })}
            options={STATUS_OPTIONS.map((option) => ({ label: t(`traces.statusOptions.${option.label}`), value: option.value }))}
            className="w-[120px]"
            size="middle"
          />
        </label>

        <Button type="primary" loading={loading} onClick={onSearch}>
          {t('traces.filters.search')}
        </Button>
        <Button onClick={onReset}>{t('traces.filters.reset')}</Button>
      </div>
    </div>
  )
}
