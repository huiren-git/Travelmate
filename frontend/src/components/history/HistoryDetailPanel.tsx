import type { TravelHistory } from '../../types/history'
import { useHistoryOutletStore } from '../../store/useHistoryOutletStore'
import type { HistoryOutletKey } from '../../types/history'
import { HistoryMapCard } from './HistoryMapCard'
import { HistoryOutletPanel } from './HistoryOutletPanel'
import { HistoryTripInfoCard } from './HistoryTripInfoCard'

type HistoryDetailPanelProps = {
  history: TravelHistory
}

export function HistoryDetailPanel({ history }: HistoryDetailPanelProps) {
  const activeOutlet = useHistoryOutletStore((state) => state.activeOutlet)
  const showRoute = useHistoryOutletStore((state) => state.showRoute)
  const showExpense = useHistoryOutletStore((state) => state.showExpense)
  const setActiveOutlet = (outlet: HistoryOutletKey) => {
    if (outlet === 'route') showRoute()
    else showExpense()
  }

  return (
    <section className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-6">
      <div className="mx-auto flex max-w-[1040px] flex-col gap-5">
        <HistoryMapCard history={history} />
        <HistoryTripInfoCard activeOutlet={activeOutlet} history={history} onOutletChange={setActiveOutlet} />
        <HistoryOutletPanel activeOutlet={activeOutlet} history={history} />
      </div>
    </section>
  )
}
