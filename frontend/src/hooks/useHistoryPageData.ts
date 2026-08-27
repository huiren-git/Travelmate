import { useEffect, useMemo, useState } from 'react'
import {
  fetchSessionSnapshot,
  fetchSessions,
  type SessionSnapshotBlackboard,
} from '../api/sessions'
import type { TravelHistory } from '../types/history'
import {
  emptyTravelHistory,
  enrichTravelHistoryFromSnapshot,
  mapSessionItemToTravelHistory,
} from '../utils/snapshotToHistory'

export function useHistoryPageData() {
  const [histories, setHistories] = useState<TravelHistory[]>([])
  // 已拉取过快照并补全的详情，按 thread_id 缓存，避免重复请求
  const [enrichedById, setEnrichedById] = useState<Record<string, TravelHistory>>({})
  const [selectedHistoryId, setSelectedHistoryId] = useState('')
  const [isLoadingList, setIsLoadingList] = useState(true)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  // 1. 挂载时拉取会话列表（GET /api/v1/sessions）
  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    async function loadList() {
      setIsLoadingList(true)
      try {
        const { sessions } = await fetchSessions({ limit: 50, signal: controller.signal })
        if (cancelled) return
        const mapped = sessions.map(mapSessionItemToTravelHistory)
        setHistories(mapped)
        setSelectedHistoryId((current) => current || mapped[0]?.id || '')
      } catch {
        if (!cancelled) setHistories([])
      } finally {
        if (!cancelled) setIsLoadingList(false)
      }
    }

    loadList()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [])

  // 选中条目：优先用已缓存的补全详情，否则回退到列表最小条目
  const selectedHistory = useMemo<TravelHistory | undefined>(() => {
    if (!selectedHistoryId) return undefined
    return enrichedById[selectedHistoryId] ?? histories.find((history) => history.id === selectedHistoryId)
  }, [selectedHistoryId, histories, enrichedById])

  // 2. 选中会话后拉取快照（GET /api/v1/sessions/{id}/snapshot）并映射补全
  useEffect(() => {
    if (!selectedHistoryId) return
    // 已缓存则不再重复拉取
    if (enrichedById[selectedHistoryId]) return

    let cancelled = false
    const controller = new AbortController()
    setIsLoadingDetail(true)
    setDetailError(null)

    fetchSessionSnapshot(selectedHistoryId, controller.signal)
      .then((snapshot) => {
        if (cancelled) return
        const blackboard: SessionSnapshotBlackboard = snapshot?.state?.blackboard ?? {}
        const base =
          histories.find((history) => history.id === selectedHistoryId) ??
          emptyTravelHistory(selectedHistoryId)
        const enriched = enrichTravelHistoryFromSnapshot(base, blackboard)
        setEnrichedById((current) => ({ ...current, [selectedHistoryId]: enriched }))
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setDetailError(error instanceof Error ? error.message : '获取行程详情失败')
      })
      .finally(() => {
        if (!cancelled) setIsLoadingDetail(false)
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [selectedHistoryId, enrichedById, histories])

  function selectHistory(historyId: string) {
    if (historyId === selectedHistoryId) return
    setSelectedHistoryId(historyId)
  }

  return {
    histories,
    selectedHistory,
    selectedHistoryId,
    setSelectedHistoryId: selectHistory,
    isLoadingList,
    isLoadingDetail,
    detailError,
  }
}

export type HistoryPageData = ReturnType<typeof useHistoryPageData>
