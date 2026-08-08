import { Layout } from 'antd'
import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AppHeader } from '../components/common/AppHeader'
import { ProfileInfoCard } from '../components/profile/ProfileInfoCard'
import { ProfileSidebarNav } from '../components/profile/ProfileSidebarNav'
import type { ProfilePageData } from '../hooks/useProfilePageData'
import { useProfileOutletStore } from '../store/useProfileOutletStore'
import { travelmateTheme } from '../utils/theme.tsx'
import { getProfileOutletFromPathname, profileRouteByOutlet } from '../utils/profileRoutes'

const { Content } = Layout

type ProfileLayoutProps = ProfilePageData

export function ProfileLayout({ preferences, profile, profileStats, setPreferences, setSettings, settings }: ProfileLayoutProps) {
  const setActiveOutlet = useProfileOutletStore((state) => state.setActiveOutlet)
  const location = useLocation()
  const navigate = useNavigate()
  const activeOutlet = getProfileOutletFromPathname(location.pathname)

  useEffect(() => {
    setActiveOutlet(activeOutlet)
  }, [activeOutlet, setActiveOutlet])

  return (
    <Layout className="h-screen" style={{ background: travelmateTheme.bg }}>
      <AppHeader colors={travelmateTheme} />
      <Content className="h-[calc(100vh-72px)] overflow-hidden bg-slate-50 p-6">
        <main className="mx-auto h-full max-w-[1120px]">
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
            <div className="shrink-0 border-b border-slate-100 bg-slate-50/60 p-5">
              <ProfileInfoCard profile={profile} stats={profileStats} />
            </div>

            <div className="flex min-h-0 flex-1">
              <ProfileSidebarNav
                activeOutlet={activeOutlet}
                onOutletChange={(outlet) => navigate(profileRouteByOutlet[outlet])}
              />
              <div className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-5">
                <Outlet
                  context={{
                    preferences,
                    profile,
                    setPreferences,
                    setSettings,
                    settings,
                  }}
                />
              </div>
            </div>
          </section>
        </main>
      </Content>
    </Layout>
  )
}
