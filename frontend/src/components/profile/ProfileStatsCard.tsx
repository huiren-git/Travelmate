import type { ProfileTravelStats } from '../../types/profile'

type ProfileStatsCardProps = {
  stats: ProfileTravelStats
}

const statItems: Array<{
  key: keyof ProfileTravelStats
  label: string
  suffix: string
}> = [
  { key: 'tripCount', label: '总行程次数', suffix: '次' },
  { key: 'visitedCityCount', label: '去过城市', suffix: '个' },
  { key: 'totalDays', label: '累计天数', suffix: '天' },
]

export function ProfileStatsCard({ stats }: ProfileStatsCardProps) {
  return (
    <div className="grid shrink-0 grid-cols-3 overflow-hidden rounded-xl border border-slate-100 bg-slate-50">
      {statItems.map((item, index) => (
        <div
          key={item.key}
          className={[
            'min-w-[104px] px-4 py-3 text-center',
            index > 0 ? 'border-l border-slate-200' : '',
          ].join(' ')}
        >
          <div className="text-[12px] text-slate-500">{item.label}</div>
          <div className="mt-1 text-[20px] font-bold leading-tight text-slate-900">
            {stats[item.key]}
            <span className="ml-1 text-[12px] font-medium text-slate-500">{item.suffix}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
