import { Popover, Table } from 'antd'
import type { TableProps } from 'antd'
import { Link } from 'react-router-dom'
import type { TraceListItem } from '../../types/trace'
import { TraceQuickPopoverContent } from './TraceQuickPopover'
import { TraceStatusTag } from './TraceStatusTag'
import { formatDurationSeconds, formatTokens } from '../../utils/traceFormat'
import { useI18n } from '../../i18n'

type TracesTableProps = {
  traces: TraceListItem[]
  loading?: boolean
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number, pageSize: number) => void
}

export function TracesTable({ traces, loading, page, pageSize, total, onPageChange }: TracesTableProps) {
  const { t } = useI18n()
  const columns: TableProps<TraceListItem>['columns'] = [
    {
      title: t('traces.table.status'),
      dataIndex: 'status',
      key: 'status',
      width: 88,
      render: (status: TraceListItem['status']) => <TraceStatusTag status={status} />,
    },
    {
      title: t('traces.table.traceId'),
      dataIndex: 'trace_id',
      key: 'trace_id',
      width: 170,
      render: (traceId: string) => (
        <span className="font-mono text-[12px] text-slate-700 dark:text-slate-300" title={traceId}>
          {traceId}
        </span>
      ),
    },
    {
      title: t('traces.table.userSession'),
      key: 'session',
      width: 220,
      render: (_: unknown, record: TraceListItem) => (
        <div className="flex flex-col leading-tight">
          <span className="text-[12px] text-slate-700 dark:text-slate-300">{record.user_id}</span>
          <span className="truncate font-mono text-[11px] text-slate-400 dark:text-slate-500" title={record.thread_id}>
            {record.thread_id}
          </span>
        </div>
      ),
    },
    {
      title: t('traces.table.inputSummary'),
      dataIndex: 'input_message',
      key: 'input_message',
      ellipsis: true,
      render: (text: string | null) => (
        <span className="text-[13px] text-slate-700 dark:text-slate-300" title={text ?? ''}>
          {text || '—'}
        </span>
      ),
    },
    {
      title: t('traces.table.span'),
      dataIndex: 'span_count',
      key: 'span_count',
      width: 70,
      render: (count: number) => <span className="font-mono text-[12px] text-slate-700 dark:text-slate-300">{count}</span>,
    },
    {
      title: t('traces.table.metrics'),
      key: 'metrics',
      width: 150,
      render: (_: unknown, record: TraceListItem) => (
        <div className="flex flex-col leading-tight">
          <span className="font-mono text-[12px] text-slate-700 dark:text-slate-300">{formatDurationSeconds(record.duration_seconds)}</span>
          <span className="font-mono text-[11px] text-slate-400 dark:text-slate-500">{formatTokens(record.total_tokens)} tokens</span>
        </div>
      ),
    },
    {
      title: t('traces.table.error'),
      dataIndex: 'error_message',
      key: 'error_message',
      width: 160,
      ellipsis: true,
      render: (text: string | null) =>
        text ? (
          <span className="text-[12px] text-rose-600 dark:text-rose-300" title={text}>
            {text}
          </span>
        ) : (
          <span className="text-[12px] text-slate-300 dark:text-slate-600">—</span>
        ),
    },
    {
      title: t('traces.table.action'),
      key: 'action',
      width: 130,
      fixed: 'right',
      render: (_: unknown, record: TraceListItem) => (
        <div className="flex items-center gap-3">
          <Popover
            trigger="click"
            placement="leftTop"
            content={<TraceQuickPopoverContent traceId={record.trace_id} />}
            overlayClassName="trace-quick-popover"
          >
            <button
              type="button"
              aria-label={t('traces.table.preview')}
              className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-100"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </Popover>
          <Link
            to={`/traces/${record.trace_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[13px] text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
          >
            {t('traces.table.viewDetail')}
          </Link>
        </div>
      ),
    },
  ]

  return (
    <Table<TraceListItem>
      rowKey="trace_id"
      columns={columns}
      dataSource={traces}
      loading={loading}
      pagination={{
        current: page,
        pageSize,
        total,
        showSizeChanger: true,
        showTotal: (count) => t('traces.table.total', { t: count }),
        onChange: onPageChange,
      }}
      scroll={{ x: 1080 }}
      size="middle"
      className="traces-table"
    />
  )
}
