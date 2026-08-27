import type { DataAction } from '../types/profile'

export function getProfileActionConfirmTitle(action: DataAction) {
  return action.danger ? `确认${action.title}？` : action.title
}

export function getProfileActionConfirmContent(action: DataAction) {
  if (action.id === 'clear-history') {
    return '将删除当前账号下保存的全部历史行程记录，删除后无法恢复。'
  }

  if (action.id === 'logout-account') {
    return '账号注销后将无法继续使用当前身份登录 Travelmate。'
  }

  if (action.id === 'export-history') {
    return '系统将准备全部历史行程数据的导出文件。'
  }

  if (action.id === 'reset-cache') {
    return '本地缓存会被重置，账号资料和云端历史行程不会被删除。'
  }

  return '该操作会影响当前保存的历史行程数据，请确认后继续。'
}
