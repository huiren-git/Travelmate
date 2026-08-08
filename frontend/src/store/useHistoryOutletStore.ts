import { create } from 'zustand'
import type { HistoryOutletKey } from '../types/history'

type HistoryOutletState = {
  activeOutlet: HistoryOutletKey
  showExpense: () => void
  showRoute: () => void
}

export const useHistoryOutletStore = create<HistoryOutletState>((set) => ({
  activeOutlet: 'route',
  showExpense: () => set({ activeOutlet: 'expense' }),
  showRoute: () => set({ activeOutlet: 'route' }),
}))
