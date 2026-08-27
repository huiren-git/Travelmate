import { Layout } from 'antd'
import { TraceFiltersBar } from '../components/traces/TraceFiltersBar'
import { TracesTable } from '../components/traces/TracesTable'
import type { TracesPageData } from '../hooks/useTracesPageData'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme } from '../utils/theme.tsx'

const { Content } = Layout

type TracesLayoutProps = TracesPageData

export function TracesLayout({
  draftFilters,
  traces,
  total,
  page,
  limit,
  loading,
  error,
  updateDraft,
  search,
  reset,
  changePage,
}: TracesLayoutProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)

  return (
    <Content className="h-[calc(100vh-72px)] overflow-hidden" style={{ background: colors.bg }}>
      <div className="flex h-full flex-col">
        <TraceFiltersBar
          filters={draftFilters}
          onChange={updateDraft}
          onSearch={search}
          onReset={reset}
          loading={loading}
        />

        <div className="flex-1 overflow-auto p-4">
          {error ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-[13px] text-rose-600 dark:border-rose-900 dark:bg-rose-950/40">
              {error}
            </div>
          ) : (
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
              <TracesTable
                traces={traces}
                loading={loading}
                page={page}
                pageSize={limit}
                total={total}
                onPageChange={changePage}
              />
            </div>
          )}
        </div>
      </div>
    </Content>
  )
}
