import { useCallback, useEffect, useState } from 'react'
import { fetchTraces } from '../api/traces'
import type { TraceFilters, TraceListItem } from '../types/trace'

const DEFAULT_PAGE_SIZE = 10

function formatLocalDateTime(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function buildDefaultFilters(): TraceFilters {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0)
  const end = new Date(start.getTime() + 24 * 60 * 60 * 1000)
  return {
    start_time: formatLocalDateTime(start),
    end_time: formatLocalDateTime(end),
    status: 'all',
    page: 1,
    limit: DEFAULT_PAGE_SIZE,
  }
}

export function useTracesPageData() {
  const [draftFilters, setDraftFilters] = useState<TraceFilters>(() => buildDefaultFilters())
  const [appliedFilters, setAppliedFilters] = useState<TraceFilters>(() => buildDefaultFilters())
  const [traces, setTraces] = useState<TraceListItem[]>([])
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(0)
  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState(DEFAULT_PAGE_SIZE)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | undefined>()

  const load = useCallback(async (filters: TraceFilters) => {
    setLoading(true)
    setError(undefined)
    try {
      const result = await fetchTraces(filters)
      setTraces(result.traces)
      setTotal(result.total)
      setTotalPages(result.total_pages)
      setPage(result.page)
      setLimit(result.limit)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载 Trace 列表失败')
      setTraces([])
      setTotal(0)
      setTotalPages(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(appliedFilters)
  }, [appliedFilters, load])

  const updateDraft = useCallback((patch: Partial<TraceFilters>) => {
    setDraftFilters((prev) => ({ ...prev, ...patch }))
  }, [])

  const search = useCallback(() => {
    // 触发查询时回到第一页
    setAppliedFilters({ ...draftFilters, page: 1 })
  }, [draftFilters])

  const reset = useCallback(() => {
    const defaults = buildDefaultFilters()
    setDraftFilters(defaults)
    setAppliedFilters(defaults)
  }, [])

  const changePage = useCallback(
    (nextPage: number, nextLimit: number) => {
      setAppliedFilters((prev) => ({ ...prev, page: nextPage, limit: nextLimit }))
      setDraftFilters((prev) => ({ ...prev, page: nextPage, limit: nextLimit }))
    },
    [],
  )

  return {
    draftFilters,
    traces,
    total,
    totalPages,
    page,
    limit,
    loading,
    error,
    updateDraft,
    search,
    reset,
    changePage,
  }
}

export type TracesPageData = ReturnType<typeof useTracesPageData>
