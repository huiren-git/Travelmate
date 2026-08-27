import type { ProfileTravelStats } from '../../types/profile'
import { useI18n } from '../../i18n'

type ProfileStatsCardProps = {
  stats: ProfileTravelStats
}

export function ProfileStatsCard({ stats }: ProfileStatsCardProps) {
  const { t } = useI18n()

  const statItems: Array<{
    key: keyof ProfileTravelStats
    label: string
    suffix: string
  }> = [
    { key: 'tripCount', label: t('profile.stats.tripCount'), suffix: t('profile.statsSuffix.tripCount') },
    { key: 'visitedCityCount', label: t('profile.stats.visitedCityCount'), suffix: t('profile.statsSuffix.visitedCityCount') },
    { key: 'totalDays', label: t('profile.stats.totalDays'), suffix: t('profile.statsSuffix.totalDays') },
  ]

  return (
    <div className="grid shrink-0 grid-cols-3 overflow-hidden rounded-xl border border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/60">
      {statItems.map((item, index) => (
        <div
          key={item.key}
          className={[
            'min-w-[104px] px-4 py-3 text-center',
            index > 0 ? 'border-l border-slate-200 dark:border-slate-700' : '',
          ].join(' ')}
        >
          <div className="text-[12px] text-slate-500 dark:text-slate-400">{item.label}</div>
          <div className="mt-1 text-[20px] font-bold leading-tight text-slate-900 dark:text-slate-100">
            {stats[item.key]}
            {item.suffix && <span className="ml-1 text-[12px] font-medium text-slate-500 dark:text-slate-400">{item.suffix}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}
