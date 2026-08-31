import { Layout } from 'antd'
import { ChatInput } from '../components/chat/ChatInput'
import { BudgetOverrunBubble } from '../components/chat/BudgetOverrunBubble'
import { ChatMessages } from '../components/chat/ChatMessages'
import { ConversationSider } from '../components/chat/ConversationSider'
import { NewTripEmptyState } from '../components/chat/NewTripEmptyState'
import { TripSummaryCard } from '../components/chat/TripSummaryCard'
import { TripTipsCard } from '../components/chat/TripTipsCard'
import { TripPlanSider } from '../components/itinerary/TripPlanSider'
import { TravelLogisticsCard } from '../components/itinerary/TravelLogisticsCard'
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
  isLoadingConversations,
  isTripPlanEmpty,
  isStreaming,
  isStopping,
  itinerary,
  logistics,
  confirmLogisticsItem,
  messages,
  pendingInterrupt,
  pieConicGradient,
  remaining,
  selectedDateIndex,
  selectConversation,
  setDraft,
  setSelectedDateIndex,
  setSiderCollapsed,
  setStructuredPreferences,
  sendMessage,
  stopMessage,
  resolveInterrupt,
  showNewTripEmptyState,
  startNewTrip,
  siderCollapsed,
  structuredPreferences,
  trip,
}: ChatLayoutProps) {
  return (
    <Layout hasSider className="h-[calc(100vh-72px)] overflow-hidden" style={{ background: colors.bg }}>
      <ConversationSider
        activeConversationId={activeConversationId}
        conversations={conversations}
        isLoading={isLoadingConversations}
        onConversationChange={selectConversation}
        onNewTrip={startNewTrip}
        onSiderCollapsedChange={setSiderCollapsed}
        siderCollapsed={siderCollapsed}
      />

      <Content style={{ background: colors.bg }} className="relative h-full overflow-hidden">
        <div className="h-full p-4 overflow-y-auto">
          <div className="mx-auto flex min-h-full max-w-[980px] flex-col gap-4 pb-44">
            {showNewTripEmptyState ? (
              <NewTripEmptyState />
            ) : (
              <>
                {activeConversation && trip && !isTripPlanEmpty && (
                  <TripSummaryCard conversationStatus={activeConversation.status} remaining={remaining} trip={trip} />
                )}
                <TravelLogisticsCard logistics={logistics} onConfirm={confirmLogisticsItem} />
                <ChatMessages messages={messages} primaryColor={colors.primary} />
                {pendingInterrupt && (
                  <BudgetOverrunBubble
                    payload={pendingInterrupt}
                    primaryColor={colors.primary}
                    onResolve={resolveInterrupt}
                    isResolving={isStreaming}
                  />
                )}
                {itinerary && itinerary.length > 0 && <TripTipsCard itinerary={itinerary} />}
              </>
            )}
          </div>
        </div>

        <ChatInput
          accentColor={colors.accent}
          draft={draft}
          onDraftChange={setDraft}
          onSend={sendMessage}
          onStop={stopMessage}
          isStreaming={isStreaming}
          isStopping={isStopping}
          onStructuredPreferencesChange={setStructuredPreferences}
          structuredPreferences={structuredPreferences}
        />
      </Content>

      <TripPlanSider
        activeDate={activeDate}
        currentItems={currentItems}
        datesList={datesList}
        expensesByCategory={expensesByCategory}
        isEmpty={isTripPlanEmpty}
        onSelectedDateIndexChange={setSelectedDateIndex}
        pieConicGradient={pieConicGradient}
        selectedDateIndex={selectedDateIndex}
        spentCny={trip?.spentCny ?? 0}
      />
    </Layout>
  )
}
