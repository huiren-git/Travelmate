import { Button, Layout, List } from 'antd'
import { MenuFoldOutlined, MenuUnfoldOutlined, PlusOutlined } from '@ant-design/icons'
import { ConversationStatusTag } from '../common/StatusTags'
import type { Conversation } from '../../types/chat'

const { Sider } = Layout

type ConversationSiderProps = {
  activeConversationId: string
  conversations: Conversation[]
  onConversationChange: (conversationId: string) => void
  onSiderCollapsedChange: (collapsed: boolean) => void
  siderCollapsed: boolean
}

export function ConversationSider({
  activeConversationId,
  conversations,
  onConversationChange,
  onSiderCollapsedChange,
  siderCollapsed,
}: ConversationSiderProps) {
  return (
    <Sider
      collapsible
      collapsed={siderCollapsed}
      onCollapse={(value) => onSiderCollapsedChange(value)}
      trigger={null}
      width={280}
      collapsedWidth={64}
      theme="light"
      className="relative border-r border-slate-200 transition-all duration-300"
    >
      <div className="flex h-full flex-col justify-between p-3">
        <div>
          <div className="mb-3 flex items-center justify-between px-1">
            {!siderCollapsed && <span className="text-[12px] font-medium text-slate-500">Conversations</span>}
            <Button
              type="text"
              size="small"
              icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => onSiderCollapsedChange(!siderCollapsed)}
              className="text-slate-500 hover:text-slate-800"
            />
          </div>

          <Button type="primary" icon={<PlusOutlined />} className="w-full rounded-xl shadow-sm flex items-center justify-center">
            {!siderCollapsed && <span>New Trip</span>}
          </Button>

          <div className="mt-3">
            <List
              dataSource={conversations}
              split={false}
              renderItem={(item) => {
                const active = item.id === activeConversationId
                return (
                  <List.Item className="p-0 mb-1">
                    <button
                      type="button"
                      onClick={() => onConversationChange(item.id)}
                      className={[
                        'w-full rounded-xl p-2 text-left transition flex items-center justify-between gap-2',
                        active ? 'text-slate-900 ring-1' : 'hover:bg-slate-50 text-slate-700',
                      ].join(' ')}
                      style={
                        active
                          ? { background: 'rgba(97, 122, 148, 0.08)', borderColor: 'rgba(0, 113, 235, 0.22)' }
                          : undefined
                      }
                    >
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <div className="h-2 w-2 rounded-full shrink-0 bg-blue-500" />
                        {!siderCollapsed && <div className="truncate text-[14px] font-medium">{item.title}</div>}
                      </div>
                      {!siderCollapsed && (
                        <div className="shrink-0 flex items-center gap-1.5">
                          <ConversationStatusTag status={item.status} />
                        </div>
                      )}
                    </button>
                  </List.Item>
                )
              }}
            />
          </div>
        </div>
      </div>
    </Sider>
  )
}
