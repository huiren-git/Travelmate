import { Button, Card } from 'antd'
import { SettingOutlined, SlidersOutlined } from '@ant-design/icons'
import type { ProfileOutletKey } from '../../types/profile'
import { useI18n } from '../../i18n'

type ProfileActionCardsProps = {
  activeOutlet: ProfileOutletKey
  onOutletChange: (outlet: ProfileOutletKey) => void
}

export function ProfileActionCards({ activeOutlet, onOutletChange }: ProfileActionCardsProps) {
  const { t } = useI18n()

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card
        className={[
          'rounded-2xl border shadow-sm transition',
          activeOutlet === 'preferences' ? 'border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/40' : 'border-transparent bg-white dark:bg-slate-900',
        ].join(' ')}
        styles={{ body: { padding: 20 } }}
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[18px] font-bold text-slate-900 dark:text-slate-100">
              <SlidersOutlined className="text-blue-600" />
              {t('profile.myPreferences')}
            </div>
            <div className="mt-2 text-[13px] text-slate-500 dark:text-slate-400">{t('profile.preferencesDesc')}</div>
          </div>
          <Button type={activeOutlet === 'preferences' ? 'primary' : 'default'} onClick={() => onOutletChange('preferences')}>
            {t('profile.open')}
          </Button>
        </div>
      </Card>

      <Card
        className={[
          'rounded-2xl border shadow-sm transition',
          activeOutlet === 'settings' ? 'border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/40' : 'border-transparent bg-white dark:bg-slate-900',
        ].join(' ')}
        styles={{ body: { padding: 20 } }}
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[18px] font-bold text-slate-900 dark:text-slate-100">
              <SettingOutlined className="text-blue-600" />
              {t('profile.nav.settings')}
            </div>
            <div className="mt-2 text-[13px] text-slate-500 dark:text-slate-400">{t('profile.settingsDesc')}</div>
          </div>
          <Button type={activeOutlet === 'settings' ? 'primary' : 'default'} onClick={() => onOutletChange('settings')}>
            {t('profile.open')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
