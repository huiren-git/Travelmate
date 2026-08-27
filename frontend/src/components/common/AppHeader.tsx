import { Avatar, Button, Layout } from 'antd'
import {
  ApartmentOutlined,
  CompassOutlined,
  HistoryOutlined,
  MessageOutlined,
  SettingOutlined,
  SlidersOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { userProfile } from '../../assets/profile/profileData'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { getTravelmateTheme } from '../../utils/theme'
import { useI18n } from '../../i18n'

const { Header } = Layout

export function AppHeader() {
  const navigate = useNavigate()
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const { t } = useI18n()

  return (
    <Header
      style={{ height: 72, padding: '0 20px', backgroundColor: colors.surface, lineHeight: 'normal' }}
      className="flex items-center justify-between border-b shadow-sm"
    >
      <button
        type="button"
        className="flex cursor-pointer items-center gap-3 text-left"
        onClick={() => navigate('/')}
        aria-label={t('header.backHome')}
      >
        <div
          className="h-9 w-9 rounded-xl shadow-sm"
          style={{ backgroundImage: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primary2} 100%)` }}
        />
        <div className="flex flex-col leading-tight">
          <div className="text-[16px] font-semibold" style={{ color: colors.textPrimary }}>
            Travelmate
          </div>
          <div className="text-[12px]" style={{ color: colors.textSecondary }}>
            AI Travel Assistant
          </div>
        </div>
      </button>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="ml-2 flex items-center gap-2 rounded-full px-2 py-1 transition-colors"
          style={{ color: colors.textPrimary }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = colors.surfaceMuted)}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          onClick={() => navigate('/profile/preferences')}
          aria-label={t('header.openProfile')}
        >
          <Avatar size={36} src={userProfile.avatarUrl} icon={<UserOutlined />} style={{ backgroundColor: colors.surfaceMuted, color: colors.textPrimary }} />
          <span className="max-w-[140px] truncate text-[14px] font-medium" style={{ color: colors.textPrimary }}>
            {userProfile.username}
          </span>
        </button>
        <Button type="text" icon={<MessageOutlined />} style={{ color: colors.textPrimary }} onClick={() => navigate('/chat')}>
          {t('header.chat')}
        </Button>
        <Button type="text" icon={<HistoryOutlined />} style={{ color: colors.textPrimary }} onClick={() => navigate('/history')}>
          {t('header.history')}
        </Button>
        <Button type="text" icon={<CompassOutlined />} style={{ color: colors.textPrimary }} onClick={() => navigate('/reference')}>
          {t('header.reference')}
        </Button>
        <Button type="text" icon={<ApartmentOutlined />} style={{ color: colors.textPrimary }} onClick={() => navigate('/traces')}>
          {t('header.traces')}
        </Button>
        <Button type="text" icon={<SlidersOutlined />} style={{ color: colors.textPrimary }} onClick={() => navigate('/profile/preferences')}>
          {t('header.preferences')}
        </Button>
        <Button type="text" icon={<SettingOutlined />} style={{ color: colors.textPrimary }} onClick={() => navigate('/profile/settings')}>
          {t('header.settings')}
        </Button>
      </div>
    </Header>
  )
}
