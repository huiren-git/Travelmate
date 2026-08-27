import { Avatar } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import type { ChatMessage } from '../../types/chat'

type ChatMessagesProps = {
  messages: ChatMessage[]
  primaryColor: string
}

export function ChatMessages({ messages, primaryColor }: ChatMessagesProps) {
  return (
    <div className="space-y-4 py-2">
      {messages.map((message) => {
        const isUser = message.role === 'user'
        return (
          <div key={message.id} className={['flex gap-3', isUser ? 'justify-end' : 'justify-start'].join(' ')}>
            {!isUser && (
              <Avatar size={36} className="text-white shrink-0 shadow-sm" style={{ background: primaryColor }}>
                T
              </Avatar>
            )}
            <div
              className={[
                'max-w-[80%] rounded-2xl px-4 py-3 shadow-sm',
                isUser
                  ? 'text-white'
                  : 'bg-white text-slate-800 ring-1 ring-slate-100 dark:bg-slate-800 dark:text-slate-100 dark:ring-slate-700',
              ].join(' ')}
              style={isUser ? { background: primaryColor } : undefined}
            >
              <div className="whitespace-pre-wrap text-[14px] leading-relaxed">{message.content}</div>
              <div className={['mt-1 text-[11px]', isUser ? 'text-white/80' : 'text-slate-400 dark:text-slate-500'].join(' ')}>
                {message.time}
              </div>
            </div>
            {isUser && (
              <Avatar
                size={36}
                className="bg-slate-200 text-slate-700 shrink-0 dark:bg-slate-700 dark:text-slate-200"
                icon={<UserOutlined />}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
