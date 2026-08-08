import { Avatar, Card } from 'antd'
import { EnvironmentOutlined } from '@ant-design/icons'
import type { ProfileTravelStats, UserProfile } from '../../types/profile'
import { ProfileStatsCard } from './ProfileStatsCard'

type ProfileInfoCardProps = {
  profile: UserProfile
  stats: ProfileTravelStats
}

export function ProfileInfoCard({ profile, stats }: ProfileInfoCardProps) {
  return (
    <Card className="rounded-2xl border-0 shadow-sm" styles={{ body: { padding: 24 } }}>
      <div className="flex items-center justify-between gap-6">
        <div className="flex min-w-0 items-center gap-5">
          <Avatar size={88} src={profile.avatarUrl} className="bg-blue-50 text-blue-600" />
          <div className="min-w-0">
            <div className="text-[26px] font-bold leading-tight text-slate-900">{profile.nickname}</div>
            <div className="mt-2 text-[14px] text-slate-500">@{profile.username}</div>
            <div className="mt-1 flex items-center gap-1 text-[14px] text-slate-500">
              <EnvironmentOutlined className="text-blue-500" />
              <span>{profile.currentCity}</span>
            </div>
          </div>
        </div>
        <ProfileStatsCard stats={stats} />
      </div>
    </Card>
  )
}
