import { Button } from 'antd'
import { HistoryOutlined, SettingOutlined, SlidersOutlined } from '@ant-design/icons'
import type { ProfileOutletKey } from '../../types/profile'

type ProfileSidebarNavProps = {
  activeOutlet: ProfileOutletKey
  onOutletChange: (outlet: ProfileOutletKey) => void
}

const navItems: Array<{
  key: ProfileOutletKey
  label: string
  icon: React.ReactNode
}> = [
  { key: 'preferences', label: '我的偏好', icon: <SlidersOutlined /> },
  { key: 'history', label: '旅行历史', icon: <HistoryOutlined /> },
  { key: 'settings', label: '设置', icon: <SettingOutlined /> },
]

export function ProfileSidebarNav({ activeOutlet, onOutletChange }: ProfileSidebarNavProps) {
  return (
    <aside className="w-[240px] shrink-0 border-r border-slate-100 p-4">
      <nav className="flex flex-col gap-2">
        {navItems.map((item) => {
          const active = item.key === activeOutlet

          return (
            <Button
              key={item.key}
              type={active ? 'primary' : 'text'}
              icon={item.icon}
              className={[
                'h-11 justify-start rounded-xl text-left',
                active ? 'shadow-sm' : 'text-slate-600 hover:bg-slate-50',
              ].join(' ')}
              onClick={() => onOutletChange(item.key)}
            >
              {item.label}
            </Button>
          )
        })}
      </nav>
    </aside>
  )
}
