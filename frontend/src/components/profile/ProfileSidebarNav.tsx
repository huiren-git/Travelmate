import { Button } from 'antd'
import { HistoryOutlined, SettingOutlined, SlidersOutlined } from '@ant-design/icons'
import type { ProfileOutletKey } from '../../types/profile'
import { useI18n } from '../../i18n'

type ProfileSidebarNavProps = {
  activeOutlet: ProfileOutletKey
  onOutletChange: (outlet: ProfileOutletKey) => void
}

export function ProfileSidebarNav({ activeOutlet, onOutletChange }: ProfileSidebarNavProps) {
  const { t } = useI18n()

  const navItems: Array<{
    key: ProfileOutletKey
    label: string
    icon: React.ReactNode
  }> = [
    { key: 'preferences', label: t('profile.nav.preferences'), icon: <SlidersOutlined /> },
    { key: 'history', label: t('profile.nav.history'), icon: <HistoryOutlined /> },
    { key: 'settings', label: t('profile.nav.settings'), icon: <SettingOutlined /> },
  ]

  return (
    <aside className="w-[240px] shrink-0 border-r border-slate-100 p-4 dark:border-slate-800">
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
                active ? 'shadow-sm' : 'text-slate-600 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800',
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
