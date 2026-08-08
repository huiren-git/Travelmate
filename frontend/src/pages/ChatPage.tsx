import { ChatLayout } from '../layouts/ChatLayout'
import { useChatPageState } from '../hooks/useChatPageState'

export default function TravelmateDashboardPage() {
  const chatPageState = useChatPageState()

  return <ChatLayout {...chatPageState} />
}
