import { Button, Layout, List } from 'antd'
import { MenuFoldOutlined, MenuUnfoldOutlined, PlusOutlined } from '@ant-design/icons'
import { ConversationStatusTag } from '../common/StatusTags'
import type { Conversation } from '../../types/chat'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { resolveTheme } from '../../utils/theme'
import { useI18n } from '../../i18n'

const { Sider } = Layout

type ConversationSiderProps = {
  activeConversationId: string
  conversations: Conversation[]
  isLoading?: boolean
  onConversationChange: (conversationId: string) => void
  onNewTrip: () => void
  onSiderCollapsedChange: (collapsed: boolean) => void
  siderCollapsed: boolean
}

export function ConversationSider({
  activeConversationId,
  conversations,
  isLoading = false,
  onConversationChange,
  onNewTrip,
  onSiderCollapsedChange,
  siderCollapsed,
}: ConversationSiderProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const resolved = resolveTheme(theme)
  const { t } = useI18n()
  return (
    <Sider
      collapsible
      collapsed={siderCollapsed}
      onCollapse={(value) => onSiderCollapsedChange(value)}
      trigger={null}
      width={280}
      collapsedWidth={64}
      theme={resolved === 'dark' ? 'dark' : 'light'}
      className="relative border-r border-slate-200 bg-white transition-all duration-300 dark:border-slate-700 dark:bg-slate-900"
    >
      <div className="flex h-full flex-col justify-between p-3">
        <div>
          <div className="mb-3 flex items-center justify-between px-1">
            {!siderCollapsed && (
              <span className="text-[12px] font-medium text-slate-500 dark:text-slate-400">{t('chat.conversations')}</span>
            )}
            <Button
              type="text"
              size="small"
              icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => onSiderCollapsedChange(!siderCollapsed)}
              className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
            />
          </div>

          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={onNewTrip}
            className="w-full rounded-xl shadow-sm flex items-center justify-center"
          >
            {!siderCollapsed && <span>{t('chat.newTrip')}</span>}
          </Button>

          <div className="mt-3">
            {!siderCollapsed && isLoading && conversations.length === 0 ? (
              <div className="px-1 py-2 text-[12px] text-slate-400 dark:text-slate-500">{t('chat.loadingHistory')}</div>
            ) : (
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
                          active
                            ? 'text-slate-900 ring-1 dark:text-slate-100'
                            : 'hover:bg-slate-50 text-slate-700 dark:hover:bg-slate-800 dark:text-slate-300',
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
            )}
          </div>
        </div>
      </div>
    </Sider>
  )
}
