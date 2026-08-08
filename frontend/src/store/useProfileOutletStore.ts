import { create } from 'zustand'
import type { ProfileOutletKey } from '../types/profile'

type ProfileOutletState = {
  activeOutlet: ProfileOutletKey
  setActiveOutlet: (outlet: ProfileOutletKey) => void
}

export const useProfileOutletStore = create<ProfileOutletState>((set) => ({
  activeOutlet: 'preferences',
  setActiveOutlet: (outlet) => set({ activeOutlet: outlet }),
}))
