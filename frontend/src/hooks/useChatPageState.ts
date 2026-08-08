import { useMemo, useState } from 'react'
import {
  assistantReplyContent,
  conversations,
  expensesByCategory,
  initialMessages,
  itinerary,
  trip,
} from '../store/chatStore'
import type { ChatMessage } from '../types/chat'
import { groupItineraryByDate } from '../utils/itinerary'
import { buildPieConicGradient } from '../utils/pie'
import { travelmateTheme } from '../utils/theme.tsx'

function formatMessageTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

export function useChatPageState() {
  const colors = travelmateTheme
  const [siderCollapsed, setSiderCollapsed] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState(conversations[0]?.id ?? '')
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [draft, setDraft] = useState('')
  const [selectedDateIndex, setSelectedDateIndex] = useState(0)

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? conversations[0],
    [activeConversationId],
  )

  const itineraryGroupedByDate = useMemo(() => groupItineraryByDate(itinerary), [])
  const datesList = useMemo(() => Object.keys(itineraryGroupedByDate), [itineraryGroupedByDate])
  const activeDate = datesList[selectedDateIndex] || datesList[0] || ''
  const currentItems = itineraryGroupedByDate[activeDate] || []
  const remaining = Math.max(0, trip.budgetCny - trip.spentCny)
  const pieConicGradient = useMemo(() => buildPieConicGradient(expensesByCategory), [])

  function sendMessage() {
    const content = draft.trim()
    if (!content) return

    const nextUser: ChatMessage = {
      id: `m-${Date.now()}`,
      role: 'user',
      content,
      time: formatMessageTime(),
    }

    setMessages((previousMessages) => [
      ...previousMessages,
      nextUser,
      {
        id: `m-a-${Date.now()}`,
        role: 'assistant',
        content: assistantReplyContent,
        time: formatMessageTime(),
      },
    ])
    setDraft('')
  }

  return {
    activeConversation,
    activeConversationId,
    activeDate,
    colors,
    conversations,
    currentItems,
    datesList,
    draft,
    expensesByCategory,
    messages,
    pieConicGradient,
    remaining,
    selectedDateIndex,
    setActiveConversationId,
    setDraft,
    setSelectedDateIndex,
    setSiderCollapsed,
    sendMessage,
    siderCollapsed,
    trip,
  }
}

export type ChatPageState = ReturnType<typeof useChatPageState>
