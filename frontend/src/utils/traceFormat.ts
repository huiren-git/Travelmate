/** 毫秒耗时格式化：→ 1.2s / 1m30s / 0s */
export function formatDuration(ms: number | null | undefined) {
  if (ms == null || ms <= 0) return '0s'
  const seconds = ms / 1000
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60)
    const rest = Math.round(seconds % 60)
    return `${minutes}m${rest}s`
  }
  return `${seconds.toFixed(1)}s`
}

/** 秒级耗时格式化（列表项 duration_seconds 用）：→ 1.2s / 1m30s / 0s */
export function formatDurationSeconds(seconds: number | null | undefined) {
  if (seconds == null || seconds <= 0) return '0s'
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60)
    const rest = Math.round(seconds % 60)
    return `${minutes}m${rest}s`
  }
  return `${seconds.toFixed(1)}s`
}

export function formatTokens(tokens: number | null | undefined) {
  if (tokens == null) return '0'
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k`
  return String(tokens)
}

export function formatDateTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', { hour12: false })
}

/** 仅展示 HH:mm:ss */
export function formatTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}
