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
  const {
    preferences,
    profile,
    setPreferences,
    isLoadingPreferences,
    isSavingPreferences,
    preferencesError,
    savePreferences,
    dismissPreferencesError,
    histories,
    isLoadingHistories,
    historiesError,
    clearAllHistorySessions,
    exportAllHistory,
  } = useOutletContext<ProfilePageData>()

  const panel =
    outletKey === 'settings' ? (
      <SettingsOutlet
        profile={profile}
        onClearHistory={clearAllHistorySessions}
        onExportHistory={exportAllHistory}
      />
    ) : outletKey === 'history' ? (
      <TravelHistoryOutlet histories={histories} isLoading={isLoadingHistories} error={historiesError} />
    ) : (
      <PreferencesOutlet
        preferences={preferences}
        setPreferences={setPreferences}
        isLoading={isLoadingPreferences}
        isSaving={isSavingPreferences}
        error={preferencesError}
        onSave={savePreferences}
        onDismissError={dismissPreferencesError}
      />
    )

  return <div className="h-full min-h-0">{panel}</div>
}
