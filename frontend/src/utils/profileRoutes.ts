import type { ProfileOutletKey } from '../types/profile'

export const profileRouteByOutlet: Record<ProfileOutletKey, string> = {
  preferences: '/profile/preferences',
  history: '/profile/history',
  settings: '/profile/settings',
}

export function getProfileOutletFromPathname(pathname: string): ProfileOutletKey {
  const matchedOutlet = Object.entries(profileRouteByOutlet).find(([, route]) => route === pathname)?.[0]

  return (matchedOutlet as ProfileOutletKey | undefined) ?? 'preferences'
}
