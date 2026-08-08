import { useMemo, useState } from 'react'
import { initialGeneralSettings, initialPreferenceSettings, userProfile } from '../assets/profile/profileData'
import { travelHistories } from '../store/historyData'
import type { GeneralSettings, PreferenceSettings } from '../types/profile'
import { getProfileTravelStats } from '../utils/profileStats'

export function useProfilePageData() {
  const [preferences, setPreferences] = useState<PreferenceSettings>(initialPreferenceSettings)
  const [settings, setSettings] = useState<GeneralSettings>(initialGeneralSettings)
  const profileStats = useMemo(() => getProfileTravelStats(travelHistories), [])

  return {
    preferences,
    profile: userProfile,
    profileStats,
    setPreferences,
    setSettings,
    settings,
  }
}

export type ProfilePageData = ReturnType<typeof useProfilePageData>
