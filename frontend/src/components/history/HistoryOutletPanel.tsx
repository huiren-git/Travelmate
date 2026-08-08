import type { TravelHistory } from '../../types/history'
import type { HistoryOutletKey } from '../../types/history'
import { HistoryExpenseOutlet } from './HistoryExpenseOutlet'
import { HistoryRouteOutlet } from './HistoryRouteOutlet'

type HistoryOutletPanelProps = {
  activeOutlet: HistoryOutletKey
  history: TravelHistory
}

export function HistoryOutletPanel({ activeOutlet, history }: HistoryOutletPanelProps) {
  if (activeOutlet === 'expense') {
    return <HistoryExpenseOutlet history={history} />
  }

  return <HistoryRouteOutlet history={history} />
}
