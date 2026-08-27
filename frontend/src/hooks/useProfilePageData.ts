import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { initialPreferenceSettings, userProfile } from '../assets/profile/profileData'
import { fetchPreferences, replacePreferences, type PreferenceListData } from '../api/preferences'
import { deleteSession, fetchAllSessions, fetchSessionSnapshot } from '../api/sessions'
import * as XLSX from 'xlsx'
import { enrichTravelHistoryFromSnapshot, mapSessionItemToTravelHistory } from '../utils/snapshotToHistory'
import type { PreferenceSettings } from '../types/profile'
import type { TravelHistory } from '../types/history'

export type ExportFormat = 'json' | 'excel'
import { getProfileOutletFromPathname } from '../utils/profileRoutes'
import { getProfileTravelStats } from '../utils/profileStats'
import { itemsToPreferenceSettings, preferenceSettingsToItems } from '../utils/preferencesMapper'

export function useProfilePageData() {
  const [preferences, setPreferences] = useState<PreferenceSettings>(initialPreferenceSettings)
  const [isLoadingPreferences, setIsLoadingPreferences] = useState(true)
  const [isSavingPreferences, setIsSavingPreferences] = useState(false)
  const [preferencesError, setPreferencesError] = useState<string | null>(null)
  const [histories, setHistories] = useState<TravelHistory[]>([])
  const [isLoadingHistories, setIsLoadingHistories] = useState(true)
  const [historiesError, setHistoriesError] = useState<string | null>(null)
  const profileStats = useMemo(() => getProfileTravelStats(histories), [histories])
  const loadCancelled = useRef(false)

  // 挂载时拉取后端偏好并回填表单
  useEffect(() => {
    const controller = new AbortController()
    loadCancelled.current = false
    setIsLoadingPreferences(true)
    setPreferencesError(null)

    fetchPreferences(controller.signal)
      .then((data: PreferenceListData) => {
        if (loadCancelled.current) return
        setPreferences(itemsToPreferenceSettings(data.preferences))
      })
      .catch((error: unknown) => {
        if (loadCancelled.current) return
        if (error instanceof DOMException && error.name === 'AbortError') return
        setPreferencesError(error instanceof Error ? error.message : '加载偏好失败')
      })
      .finally(() => {
        if (!loadCancelled.current) setIsLoadingPreferences(false)
      })

    return () => {
      loadCancelled.current = true
      controller.abort()
    }
  }, [])

  const loadHistories = useCallback(async (signal?: AbortSignal) => {
    setIsLoadingHistories(true)
    setHistoriesError(null)

    try {
      const sessions = await fetchAllSessions(signal)
      const baseList = sessions.map(mapSessionItemToTravelHistory)
      const enriched = await Promise.all(
        baseList.map(async (base) => {
          try {
            const snap = await fetchSessionSnapshot(base.id, signal)
            return enrichTravelHistoryFromSnapshot(base, snap.state.blackboard)
          } catch {
            return base
          }
        }),
      )

      if (signal?.aborted) return
      setHistories(enriched)
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (signal?.aborted) return
      setHistoriesError(error instanceof Error ? error.message : '加载旅行历史失败')
    } finally {
      if (!signal?.aborted) {
        setIsLoadingHistories(false)
      }
    }
  }, [])

  // 仅在 history 子路由拉取真实旅行历史（列表 + 逐条快照补全）
  const location = useLocation()
  const activeOutlet = getProfileOutletFromPathname(location.pathname)

  useEffect(() => {
    if (activeOutlet !== 'history') return

    const controller = new AbortController()
    void loadHistories(controller.signal)

    return () => controller.abort()
  }, [activeOutlet, loadHistories])

  // 现场拉取全部会话 + 逐条快照，补全为可导出 TravelHistory[]。
  // 不依赖组件缓存（设置页打开时 history 子路由未必挂载过）。
  async function fetchEnrichedHistories(): Promise<TravelHistory[]> {
    const sessions = await fetchAllSessions()
    const baseList = sessions.map(mapSessionItemToTravelHistory)
    const enriched = await Promise.all(
      baseList.map(async (base) => {
        try {
          const snap = await fetchSessionSnapshot(base.id)
          return enrichTravelHistoryFromSnapshot(base, snap.state.blackboard)
        } catch {
          return base
        }
      }),
    )
    return enriched
  }

  // 触发浏览器下载一个 Blob
  function triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    URL.revokeObjectURL(url)
  }

  // 形如 20260820-1830 的时间戳，用于文件名
  function fileTimestamp(): string {
    const d = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    return (
      `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
      `-${pad(d.getHours())}${pad(d.getMinutes())}`
    )
  }

  function downloadHistoriesJson(histories: TravelHistory[]) {
    const payload = {
      exportedAt: new Date().toISOString(),
      source: 'travelmate',
      version: 1,
      count: histories.length,
      histories,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    triggerDownload(blob, `travelmate-history-${fileTimestamp()}.json`)
  }

  function downloadHistoriesExcel(histories: TravelHistory[]) {
    const workbook = XLSX.utils.book_new()

    const overview = histories.map((h) => ({
      行程ID: h.id,
      目的地: h.destination,
      标题: h.title,
      状态: h.status,
      日期区间: h.dateRange,
      出行人数: h.people,
      总花费CNY: h.totalExpenseCny,
    }))
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(overview), '行程概览')

    const route = histories.flatMap((h) =>
      h.routeItems.map((r) => ({
        行程ID: h.id,
        目的地: h.destination,
        时间: r.time,
        景点: r.attractionName,
        预估费用CNY: r.costCny,
        描述: r.description,
      })),
    )
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(route), '每日路线')

    const expense = histories.flatMap((h) =>
      h.expenseDetails.map((e) => ({
        行程ID: h.id,
        目的地: h.destination,
        日期: e.date,
        项目: e.title,
        类别: e.category,
        金额CNY: e.amountCny,
      })),
    )
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(expense), '费用明细')

    const daily = histories.flatMap((h) =>
      h.dailyExpenses.map((d) => ({
        行程ID: h.id,
        目的地: h.destination,
        日期: d.date,
        金额CNY: d.amountCny,
      })),
    )
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(daily), '每日费用')

    XLSX.writeFile(workbook, `travelmate-history-${fileTimestamp()}.xlsx`)
  }

  // 现场拉取并导出全部历史行程，按所选格式下载。
  async function exportAllHistory(format: ExportFormat = 'json') {
    const histories = await fetchEnrichedHistories()
    if (format === 'excel') {
      downloadHistoriesExcel(histories)
    } else {
      downloadHistoriesJson(histories)
    }
    return histories.length
  }

  async function clearAllHistorySessions() {
    setHistoriesError(null)

    const sessions = await fetchAllSessions()
    let deletedCount = 0
    let firstError: unknown = null

    for (const session of sessions) {
      try {
        await deleteSession(session.thread_id)
        deletedCount += 1
      } catch (error) {
        if (!firstError) {
          firstError = error
        }
      }
    }

    await loadHistories()

    if (firstError) {
      throw firstError
    }

    return deletedCount
  }

  // 保存：把当前表单整体替换到后端（手动偏好），成功后用返回值回填
  async function savePreferences() {
    setIsSavingPreferences(true)
    setPreferencesError(null)
    try {
      const items = preferenceSettingsToItems(preferences)
      const data = await replacePreferences(items)
      setPreferences(itemsToPreferenceSettings(data.preferences))
    } catch (error: unknown) {
      setPreferencesError(error instanceof Error ? error.message : '保存偏好失败')
    } finally {
      setIsSavingPreferences(false)
    }
  }

  function dismissPreferencesError() {
    setPreferencesError(null)
  }

  return {
    preferences,
    profile: userProfile,
    profileStats,
    setPreferences,
    isLoadingPreferences,
    isSavingPreferences,
    preferencesError,
    savePreferences,
    dismissPreferencesError,
    histories,
    isLoadingHistories,
    historiesError,
    clearAllHistorySessions,
    exportAllHistory,
  }
}

export type ProfilePageData = ReturnType<typeof useProfilePageData>
