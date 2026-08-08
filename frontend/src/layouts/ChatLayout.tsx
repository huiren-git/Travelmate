import { Layout } from 'antd'
import { ChatInput } from '../components/chat/ChatInput'
import { ChatMessages } from '../components/chat/ChatMessages'
import { ConversationSider } from '../components/chat/ConversationSider'
import { TripSummaryCard } from '../components/chat/TripSummaryCard'
import { TripPlanSider } from '../components/itinerary/TripPlanSider'
import type { ChatPageState } from '../hooks/useChatPageState'

const { Content } = Layout

type ChatLayoutProps = ChatPageState

export function ChatLayout({
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
}: ChatLayoutProps) {
  return (
    <Layout hasSider className="h-[calc(100vh-72px)] overflow-hidden" style={{ background: colors.bg }}>
      <ConversationSider
        activeConversationId={activeConversationId}
        conversations={conversations}
        onConversationChange={setActiveConversationId}
        onSiderCollapsedChange={setSiderCollapsed}
        siderCollapsed={siderCollapsed}
      />

      <Content style={{ background: colors.bg }} className="relative h-full overflow-hidden">
        <div className="h-full p-4 overflow-y-auto">
          <div className="mx-auto flex min-h-full max-w-[980px] flex-col gap-4 pb-28">
            <TripSummaryCard conversationStatus={activeConversation.status} remaining={remaining} trip={trip} />
            <ChatMessages messages={messages} primaryColor={colors.primary} />
          </div>
        </div>

        <ChatInput accentColor={colors.accent} draft={draft} onDraftChange={setDraft} onSend={sendMessage} />
      </Content>

      <TripPlanSider
        activeDate={activeDate}
        currentItems={currentItems}
        datesList={datesList}
        expensesByCategory={expensesByCategory}
        onSelectedDateIndexChange={setSelectedDateIndex}
        pieConicGradient={pieConicGradient}
        selectedDateIndex={selectedDateIndex}
        spentCny={trip.spentCny}
      />
    </Layout>
  )
}
