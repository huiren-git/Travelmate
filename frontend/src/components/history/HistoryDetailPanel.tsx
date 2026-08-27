import type { TravelHistory } from '../../types/history'
import { useHistoryOutletStore } from '../../store/useHistoryOutletStore'
import type { HistoryOutletKey } from '../../types/history'
import { HistoryMapCard } from './HistoryMapCard'
import { HistoryOutletPanel } from './HistoryOutletPanel'
import { HistoryTripInfoCard } from './HistoryTripInfoCard'

type HistoryDetailPanelProps = {
  history: TravelHistory
  isLoadingDetail?: boolean
}

export function HistoryDetailPanel({ history, isLoadingDetail }: HistoryDetailPanelProps) {
  const activeOutlet = useHistoryOutletStore((state) => state.activeOutlet)
  const showRoute = useHistoryOutletStore((state) => state.showRoute)
  const showExpense = useHistoryOutletStore((state) => state.showExpense)
  const setActiveOutlet = (outlet: HistoryOutletKey) => {
    if (outlet === 'route') showRoute()
    else showExpense()
  }

  return (
    <section className="relative min-w-0 flex-1 overflow-y-auto bg-slate-50 p-6 dark:bg-slate-900">
      {isLoadingDetail && (
        <div className="absolute inset-x-0 top-0 z-10 h-0.5 animate-pulse bg-blue-500" />
      )}
      <div className="mx-auto flex max-w-[1040px] flex-col gap-5">
        <HistoryMapCard history={history} />
        <HistoryTripInfoCard activeOutlet={activeOutlet} history={history} onOutletChange={setActiveOutlet} />
        <HistoryOutletPanel activeOutlet={activeOutlet} history={history} />
      </div>
    </section>
  )
}
