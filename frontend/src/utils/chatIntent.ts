export type ChatIntent = 'plan' | 'consult' | 'update_preferences' | 'replan'

export function loadingLabelForIntent(intent: unknown): string {
  switch (intent) {
    case 'consult': return '正在回答旅行问题...'
    case 'update_preferences': return '正在更新出发信息...'
    case 'replan': return '正在调整行程...'
    default: return '正在生成行程...'
  }
}

export function intentFromStreamData(value: unknown): ChatIntent | undefined {
  if (!value || typeof value !== 'object') return undefined
  const record = value as Record<string, unknown>
  const supervisor = record.supervisor as Record<string, unknown> | undefined
  const values = record.values as Record<string, unknown> | undefined
  const candidates = [record.intent, supervisor?.intent, values?.intent]
  return candidates.find((intent): intent is ChatIntent => intent === 'plan' || intent === 'consult' || intent === 'update_preferences' || intent === 'replan')
}

export function loadingLabelForStreamEvent(event: string, value: unknown): string | undefined {
  const values = value && typeof value === 'object' ? (value as Record<string, unknown>).values : undefined
  const terminalStatus = values && typeof values === 'object' ? (values as Record<string, unknown>).terminal_status : undefined
  if (event === 'done' && (terminalStatus === 'failed' || terminalStatus === 'confirmed')) return undefined
  const messages = values && typeof values === 'object' ? (values as Record<string, unknown>).messages : undefined
  const hasCompletedAiReply = event === 'done' && Array.isArray(messages) && messages.some((message) => {
    return Boolean(message && typeof message === 'object' && (message as Record<string, unknown>).type === 'ai' && (message as Record<string, unknown>).content)
  })
  if (hasCompletedAiReply) return undefined
  const intent = intentFromStreamData(value)
  return intent ? loadingLabelForIntent(intent) : undefined
}
