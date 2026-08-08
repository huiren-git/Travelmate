import { useOutletContext } from 'react-router-dom'
import type { ProfilePageData } from '../../hooks/useProfilePageData'
import type { ProfileOutletKey } from '../../types/profile'
import { PreferencesOutlet } from './PreferencesOutlet'
import { SettingsOutlet } from './SettingsOutlet'
import { TravelHistoryOutlet } from './TravelHistoryOutlet'

type ProfileOutletPanelProps = {
  outletKey: ProfileOutletKey
}

export function ProfileOutletPanel({ outletKey }: ProfileOutletPanelProps) {
  const { preferences, profile, setPreferences, setSettings, settings } = useOutletContext<ProfilePageData>()

  if (outletKey === 'settings') {
    return <SettingsOutlet profile={profile} settings={settings} setSettings={setSettings} />
  }

  if (outletKey === 'history') {
    return <TravelHistoryOutlet />
  }

  return <PreferencesOutlet preferences={preferences} setPreferences={setPreferences} />
}
