import { Avatar, Button, Layout } from 'antd'
import { HistoryOutlined, SettingOutlined, SlidersOutlined, UserOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { userProfile } from '../../assets/profile/profileData'
import type { TravelmateTheme } from '../../utils/theme.tsx'

const { Header } = Layout

type AppHeaderProps = {
  colors: TravelmateTheme
}

export function AppHeader({ colors }: AppHeaderProps) {
  const navigate = useNavigate()

  return (
    <Header
      style={{ height: 72, padding: '0 20px', backgroundColor: '#ffffff', lineHeight: 'normal' }}
      className="flex items-center justify-between bg-white shadow-sm"
    >
      <button
        type="button"
        className="flex items-center gap-3 text-left"
        onClick={() => navigate('/chat')}
        aria-label="返回聊天首页"
      >
        <div
          className="h-9 w-9 rounded-xl shadow-sm"
          style={{ backgroundImage: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.primary2} 100%)` }}
        />
        <div className="flex flex-col leading-tight">
          <div className="text-[16px] font-semibold text-slate-900">Travelmate</div>
          <div className="text-[12px] text-slate-500">AI Travel Assistant</div>
        </div>
      </button>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="ml-2 flex items-center gap-2 rounded-full px-2 py-1 transition-colors hover:bg-slate-50"
          onClick={() => navigate('/profile/preferences')}
          aria-label="打开个人中心"
        >
          <Avatar size={36} src={userProfile.avatarUrl} icon={<UserOutlined />} className="bg-slate-200 text-slate-700" />
          <span className="max-w-[140px] truncate text-[14px] font-medium text-slate-700">{userProfile.username}</span>
        </button>
        <Button type="text" icon={<HistoryOutlined />} className="text-slate-700" onClick={() => navigate('/history')}>
          History
        </Button>
        <Button
          type="text"
          icon={<SlidersOutlined />}
          className="text-slate-700"
          onClick={() => navigate('/profile/preferences')}
        >
          Preferences
        </Button>
        <Button
          type="text"
          icon={<SettingOutlined />}
          className="text-slate-700"
          onClick={() => navigate('/profile/settings')}
        >
          Settings
        </Button>
      </div>
    </Header>
  )
}
