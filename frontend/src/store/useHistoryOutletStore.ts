import { create } from 'zustand'
import type { HistoryOutletKey } from '../types/history'

type HistoryOutletState = {
  activeOutlet: HistoryOutletKey
  showExpense: () => void
  showRoute: () => void
  reset: () => void
}

export const useHistoryOutletStore = create<HistoryOutletState>((set) => ({
  activeOutlet: 'route',
  showExpense: () => set({ activeOutlet: 'expense' }),
  showRoute: () => set({ activeOutlet: 'route' }),
  reset: () => set({ activeOutlet: 'route' }),
}))
