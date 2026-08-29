import { useEffect, useMemo, useRef, useState } from 'react'
import { confirmLogistics, createChatThreadId, resumeChat, streamChat, type BudgetInterruptPayload, type ParsedSseEvent } from '../api/chat'
import { fetchSessionSnapshot, fetchSessions, mapSessionItemsToConversations, type SessionSnapshotBlackboard } from '../api/sessions'
import type { ChatMessage, Conversation, GeneratedTripPlan, StructuredPreferences } from '../types/chat'
import { adaptGeneratedTripPlan } from '../utils/chatPlanAdapter'
import { groupItineraryByDate } from '../utils/itinerary'
import { buildPieConicGradient } from '../utils/pie'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme } from '../utils/theme.tsx'
import { loadingLabelForStreamEvent } from '../utils/chatIntent'

function formatMessageTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatConversationUpdatedAt() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function conversationTitleFromMessage(message: string) {
  return message.length > 18 ? `${message.slice(0, 18)}...` : message
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function extractAiMessageContent(value: unknown): string | undefined {
  if (!isRecord(value)) {
    return undefined
  }

  const candidateMessages = [
    value.messages,
    isRecord(value.data) ? value.data.messages : undefined,
    isRecord(value.state) ? value.state.messages : undefined,
    isRecord(value.values) ? value.values.messages : undefined,
  ]

  for (const messages of candidateMessages) {
    if (!Array.isArray(messages)) {
      continue
    }

    const aiMessage = [...messages].reverse().find((message) => {
      if (!isRecord(message)) {
        return false
      }
      return message.type === 'ai' || message.role === 'assistant'
    })

    if (isRecord(aiMessage) && typeof aiMessage.content === 'string' && aiMessage.content.trim()) {
      return aiMessage.content
    }
  }

  return undefined
}

function extractDoneItineraryContent(value: unknown): string | undefined {
  if (!isRecord(value)) {
    return undefined
  }
  const source = isRecord(value.values) ? value.values : value
  if (source.terminal_status === 'failed') {
    const reason = typeof source.failure_reason === 'string' ? source.failure_reason.trim() : ''
    return reason ? `行程未通过质量校验：${reason}。请调整需求后重新生成。` : '行程未通过质量校验，未向计划面板写入任何结果。请调整需求后重新生成。'
  }
  // 优先使用后端定稿后生成的总结语文案
  if (typeof source.summary_text === 'string' && source.summary_text.trim() !== '') {
    return source.summary_text
  }
  const itinerary = source.daily_itinerary
  const budget = source.budget
  if (!itinerary && !budget) {
    return undefined
  }
  return '行程已生成，已同步到计划面板。'
}

// 从 done 事件的 snapshot.tasks 中提取预算超支中断 payload（LangGraph 把 interrupt 挂在 task.interrupts[].value）。
function extractBudgetInterruptFromDone(event: ParsedSseEvent): BudgetInterruptPayload | null {
  const data = event.data
  if (!isRecord(data)) {
    return null
  }
  const tasks = data.tasks
  if (!Array.isArray(tasks)) {
    return null
  }
  for (const task of tasks) {
    if (!isRecord(task)) {
      continue
    }
    const interrupts = task.interrupts
    if (!Array.isArray(interrupts)) {
      continue
    }
    for (const it of interrupts) {
      if (!isRecord(it)) {
        continue
      }
      const value = isRecord(it.value) ? it.value : isRecord(it.payload) ? it.payload : null
      if (value && value.type === 'budget_overrun') {
        return value as BudgetInterruptPayload
      }
    }
  }
  return null
}

function streamEventContent(event: ParsedSseEvent): string | undefined {
  const aiContent = extractAiMessageContent(event.data)
  if (aiContent) {
    return aiContent
  }

  const intentLabel = loadingLabelForStreamEvent(event.event, event.data)
  if (intentLabel) return intentLabel

  if (event.event === 'done') {
    return extractDoneItineraryContent(event.data)
  }
  if (event.event === 'stopped') {
    return '生成已停止，已保留当前部分结果。'
  }
  if (event.event === 'error') {
    const data = event.data && typeof event.data === 'object' ? (event.data as { message?: unknown }) : {}
    return typeof data.message === 'string' ? data.message : '生成失败，请稍后重试。'
  }
  if (event.event === 'node') {
    const data = event.data && typeof event.data === 'object' ? (event.data as { node?: unknown }) : {}
    return typeof data.node === 'string' ? `正在处理：${data.node}` : '正在生成行程...'
  }
  return '正在生成行程...'
}

// 从快照 blackboard.messages 还原对话历史（human→user, ai→assistant；其余跳过）。
function messagesFromBlackboard(threadId: string, blackboard: SessionSnapshotBlackboard): ChatMessage[] {
  const raw = blackboard.messages
  if (!Array.isArray(raw)) return []
  const result: ChatMessage[] = []
  raw.forEach((message, index) => {
    if (!message || typeof message !== 'object') return
    const type = message.type
    const content = message.content
    const text = typeof content === 'string' ? content : ''
    if (!text.trim()) return
    const role: 'user' | 'assistant' | undefined =
      type === 'human' ? 'user' : type === 'ai' ? 'assistant' : undefined
    if (!role) return
    result.push({
      id: `m-hydrate-${threadId}-${index}`,
      role,
      content: text,
      time: '',
    })
  })
  return result
}

export function useChatPageState() {
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const [siderCollapsed, setSiderCollapsed] = useState(false)
  const [conversationList, setConversationList] = useState<Conversation[]>([])
  const [activeConversationId, setActiveConversationId] = useState('')
  const [messagesByConversationId, setMessagesByConversationId] = useState<Record<string, ChatMessage[]>>({})
  const [isLoadingConversations, setIsLoadingConversations] = useState(true)
  const [draft, setDraft] = useState('')
  const [selectedDateIndex, setSelectedDateIndex] = useState(0)
  const [structuredPreferences, setStructuredPreferences] = useState<StructuredPreferences>()
  const [isNewTripMode, setIsNewTripMode] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [emptyTripPlanConversationIds, setEmptyTripPlanConversationIds] = useState<Set<string>>(() => new Set())
  const [generatedTripPlansByConversationId, setGeneratedTripPlansByConversationId] = useState<
    Record<string, GeneratedTripPlan>
  >({})
  // 预算超支等人机协同中断：从 done 事件的 tasks 提取，渲染为确认气泡；用户选择后调 /chat/resume 续跑。
  const [pendingInterrupt, setPendingInterrupt] = useState<BudgetInterruptPayload | null>(null)

  useEffect(() => {
    const raw = sessionStorage.getItem('reference-adoption')
    if (!raw) return
    sessionStorage.removeItem('reference-adoption')
    try {
      const { threadId, data } = JSON.parse(raw) as { threadId: string; data: unknown }
      const plan = adaptGeneratedTripPlan(data)
      setActiveConversationId(threadId)
      setConversationList((current) => current.some(x => x.id === threadId) ? current : [{ id: threadId, title: '参考行程适配', updatedAt: formatConversationUpdatedAt(), status: '已完成' }, ...current])
      if (plan) setGeneratedTripPlansByConversationId((current) => ({ ...current, [threadId]: plan }))
      const entries = (data as { values?: { adaptation_log?: Array<{ kind?: string; from?: string; to?: string }> } }).values?.adaptation_log ?? []
      setMessagesByConversationId((current) => ({ ...current, [threadId]: [{ id: `m-ref-${Date.now()}`, role: 'assistant', time: formatMessageTime(), content: `已按参考方案完成适配。${entries.map(x => `${x.kind}${x.from ? `：${x.from}` : ''}${x.to ? ` → ${x.to}` : ''}`).join('；')}` }] }))
    } catch { /* ignore stale handoff */ }
  }, [])

  // 旅行历史（左侧会话列表）由后端 GET /api/v1/sessions 提供，挂载时拉取首批。
  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    async function loadConversations() {
      setIsLoadingConversations(true)
      try {
        const { sessions } = await fetchSessions({ limit: 50, signal: controller.signal })
        if (cancelled) return
        const mapped = mapSessionItemsToConversations(sessions)
        setConversationList(mapped)
        setActiveConversationId((current) => current || mapped[0]?.id || '')
      } catch {
        if (cancelled) return
        setConversationList([])
      } finally {
        if (!cancelled) {
          setIsLoadingConversations(false)
        }
      }
    }

    loadConversations()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [])

  // 选中会话时，若本地尚无该会话消息，则从快照恢复对话历史与行程面板。
  // 方案②后，snapshot 的 blackboard.messages 已含多轮 human+ai，可直接还原中间对话栏。
  const hydratedThreadIds = useRef<Set<string>>(new Set())
  useEffect(() => {
    const threadId = activeConversationId
    if (!threadId) return
    // 已 hydrate 过，或本地已有（实时 SSE 填充过 / 新建会话占位）则跳过，避免覆盖本地状态
    if (hydratedThreadIds.current.has(threadId)) return
    if (messagesByConversationId[threadId] !== undefined) return
    hydratedThreadIds.current.add(threadId)

    let cancelled = false
    const controller = new AbortController()
    fetchSessionSnapshot(threadId, controller.signal)
      .then((snapshot) => {
        if (cancelled) return
        const blackboard: SessionSnapshotBlackboard = snapshot?.state?.blackboard ?? {}
        const restored = messagesFromBlackboard(threadId, blackboard)
        setMessagesByConversationId((current) => ({ ...current, [threadId]: restored }))

        // 同步恢复右侧行程面板
        const tripPlan = adaptGeneratedTripPlan({ values: blackboard })
        if (tripPlan) {
          setGeneratedTripPlansByConversationId((current) => ({ ...current, [threadId]: tripPlan }))
          setEmptyTripPlanConversationIds((current) => {
            const next = new Set(current)
            next.delete(threadId)
            return next
          })
        }
      })
      .catch(() => {
        if (cancelled) return
        // 拉取失败允许后续重试
        hydratedThreadIds.current.delete(threadId)
      })

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [activeConversationId, messagesByConversationId])

  const activeConversation = useMemo(
    () => conversationList.find((conversation) => conversation.id === activeConversationId) ?? conversationList[0],
    [activeConversationId, conversationList],
  )
  const messages = messagesByConversationId[activeConversationId] ?? []
  const generatedTripPlan = generatedTripPlansByConversationId[activeConversationId]
  const displayTrip = generatedTripPlan?.trip
  const displayItinerary = generatedTripPlan?.itinerary
  const displayExpensesByCategory = generatedTripPlan?.expensesByCategory
  const isTripPlanEmpty = !generatedTripPlan || emptyTripPlanConversationIds.has(activeConversationId)
  const isActiveConversationEmpty = messages.length === 0
  const showNewTripEmptyState = isTripPlanEmpty && isActiveConversationEmpty

  const itineraryGroupedByDate = useMemo(() => groupItineraryByDate(displayItinerary ?? []), [displayItinerary])
  const datesList = useMemo(() => Object.keys(itineraryGroupedByDate), [itineraryGroupedByDate])
  const activeDate = datesList[selectedDateIndex] || datesList[0] || ''
  const currentItems = itineraryGroupedByDate[activeDate] || []
  const remaining = displayTrip ? Math.max(0, displayTrip.budgetCny - displayTrip.spentCny) : 0
  const pieConicGradient = useMemo(
    () => buildPieConicGradient(displayExpensesByCategory ?? []),
    [displayExpensesByCategory],
  )

  function startNewTrip() {
    // 进入「待创建」状态：只清空中间栏，不在左侧生成条目。
    // 真正的新会话条目会在用户发送第一条消息时（sendMessage）才加入列表。
    const threadId = createChatThreadId()

    setMessagesByConversationId((current) => ({ ...current, [threadId]: [] }))
    setEmptyTripPlanConversationIds((current) => {
      const next = new Set(current)
      next.add(threadId)
      return next
    })
    setActiveConversationId(threadId)
    setIsNewTripMode(true)
    setDraft('')
    setStructuredPreferences(undefined)
    setSelectedDateIndex(0)
  }

  function selectConversation(conversationId: string) {
    setActiveConversationId(conversationId)
    setIsNewTripMode(false)
    setSelectedDateIndex(0)
  }

  async function sendMessage() {
    const content = draft.trim()
    if (!content || isStreaming) return

    const threadId = activeConversationId
    // 若当前激活的会话尚未加入左侧列表（即刚点过 New Trip 但还没发过消息），
    // 则把第一条消息作为标题，创建真正的会话条目。
    const isPendingNewTrip = !conversationList.some((conversation) => conversation.id === threadId)
    const preferencesSnapshot = structuredPreferences
    const assistantId = `m-a-${Date.now()}`

    setIsNewTripMode(false)
    setDraft('')

    if (isPendingNewTrip) {
      const newConversation: Conversation = {
        id: threadId,
        title: conversationTitleFromMessage(content),
        updatedAt: formatConversationUpdatedAt(),
        status: '进行中',
      }
      setConversationList((current) => [newConversation, ...current])
    }

    const nextUser: ChatMessage = {
      id: `m-${Date.now()}`,
      role: 'user',
      content,
      time: formatMessageTime(),
      ...(preferencesSnapshot ? { structured_input: preferencesSnapshot } : {}),
    }

    setConversationList((current) =>
      current.map((conversation) =>
        conversation.id === threadId ? { ...conversation, updatedAt: formatConversationUpdatedAt() } : conversation,
      ),
    )
    setMessagesByConversationId((current) => ({
      ...current,
      [threadId]: [
        ...(current[threadId] ?? []),
        nextUser,
        {
          id: assistantId,
          role: 'assistant',
          content: '正在生成行程...',
          time: formatMessageTime(),
        },
      ],
    }))

    setIsStreaming(true)
    try {
      await streamChat(
        {
          thread_id: threadId,
          message: content,
          current_time: new Date().toISOString(),
          ...(preferencesSnapshot ? { structured_input: preferencesSnapshot } : {}),
        },
        (event) => {
          if (event.event === 'done') {
            const generatedTripPlan = adaptGeneratedTripPlan(event.data)
            if (generatedTripPlan) {
              setGeneratedTripPlansByConversationId((current) => ({
                ...current,
                [threadId]: generatedTripPlan,
              }))
              setEmptyTripPlanConversationIds((current) => {
                const next = new Set(current)
                next.delete(threadId)
                return next
              })
            }
            // 提取预算超支等中断，渲染确认气泡（人机协同）
            const interrupt = extractBudgetInterruptFromDone(event)
            if (interrupt) {
              setPendingInterrupt(interrupt)
            }
          }

          const nextContent = streamEventContent(event)
          if (!nextContent) {
            return
          }

          setMessagesByConversationId((current) => ({
            ...current,
            [threadId]: (current[threadId] ?? []).map((message) =>
              message.id === assistantId ? { ...message, content: nextContent, time: formatMessageTime() } : message,
            ),
          }))
        },
      )
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '请求失败，请稍后重试。'
      setMessagesByConversationId((current) => ({
        ...current,
        [threadId]: (current[threadId] ?? []).map((message) =>
          message.id === assistantId ? { ...message, content: errorMessage, time: formatMessageTime() } : message,
        ),
      }))
    } finally {
      setIsStreaming(false)
    }
  }

  async function confirmLogisticsItem(itemKey: string) {
    const logistics = await confirmLogistics(activeConversationId, itemKey)
    setGeneratedTripPlansByConversationId((current) => {
      const plan = current[activeConversationId]
      if (!plan || !isRecord(logistics)) return current
      const next = adaptGeneratedTripPlan({ values: { terminal_status: 'confirmed', is_finished: true, budget: { total: plan.trip.budgetCny, detail: {} }, daily_itinerary: plan.itinerary, travel_logistics: logistics } })
      return next ? { ...current, [activeConversationId]: { ...plan, logistics: next.logistics } } : current
    })
  }

  // 用户处理超支中断：调用 /chat/resume 续跑图，并把返回的 SSE 当作普通流式消息追加到对话栏。
  async function resolveInterrupt(action: 'accept' | 'modify', hint?: string) {
    const threadId = activeConversationId
    if (!pendingInterrupt) {
      return
    }
    const assistantId = `m-i-${Date.now()}`
    setPendingInterrupt(null)
    setMessagesByConversationId((current) => ({
      ...current,
      [threadId]: [
        ...(current[threadId] ?? []),
        {
          id: assistantId,
          role: 'assistant',
          content: action === 'accept' ? '已接受超支，继续规划行程...' : '正在按您的调整重新规划行程...',
          time: formatMessageTime(),
        },
      ],
    }))
    setIsStreaming(true)
    try {
      await resumeChat(
        { thread_id: threadId, user_decision: { action, ...(hint && hint.trim() ? { hint: hint.trim() } : {}) } },
        (event) => {
          if (event.event === 'done') {
            const generatedTripPlan = adaptGeneratedTripPlan(event.data)
            if (generatedTripPlan) {
              setGeneratedTripPlansByConversationId((current) => ({ ...current, [threadId]: generatedTripPlan }))
              setEmptyTripPlanConversationIds((current) => {
                const next = new Set(current)
                next.delete(threadId)
                return next
              })
            }
          }
          const nextContent = streamEventContent(event)
          if (!nextContent) {
            return
          }
          setMessagesByConversationId((current) => ({
            ...current,
            [threadId]: (current[threadId] ?? []).map((message) =>
              message.id === assistantId ? { ...message, content: nextContent, time: formatMessageTime() } : message,
            ),
          }))
        },
      )
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '操作失败，请稍后重试。'
      setMessagesByConversationId((current) => ({
        ...current,
        [threadId]: (current[threadId] ?? []).map((message) =>
          message.id === assistantId ? { ...message, content: errorMessage, time: formatMessageTime() } : message,
        ),
      }))
    } finally {
      setIsStreaming(false)
    }
  }

  return {
    activeConversation,
    activeConversationId,
    activeDate,
    colors,
    conversations: conversationList,
    currentItems,
    datesList,
    draft,
    expensesByCategory: displayExpensesByCategory,
    isNewTripMode,
    isStreaming,
    isTripPlanEmpty,
    isLoadingConversations,
    messages,
    pieConicGradient,
    remaining,
    selectedDateIndex,
    selectConversation,
    setDraft,
    setSelectedDateIndex,
    setSiderCollapsed,
    setStructuredPreferences,
    sendMessage,
    resolveInterrupt,
    pendingInterrupt,
    showNewTripEmptyState,
    startNewTrip,
    siderCollapsed,
    structuredPreferences,
    trip: displayTrip,
    itinerary: displayItinerary,
    logistics: generatedTripPlan?.logistics,
    confirmLogisticsItem,
  }
}

export type ChatPageState = ReturnType<typeof useChatPageState>
