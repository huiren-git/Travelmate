import { Layout } from 'antd'
import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { AppHeader } from '../components/common/AppHeader'
import { ProfileInfoCard } from '../components/profile/ProfileInfoCard'
import { ProfileSidebarNav } from '../components/profile/ProfileSidebarNav'
import type { ProfilePageData } from '../hooks/useProfilePageData'
import { useProfileOutletStore } from '../store/useProfileOutletStore'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme } from '../utils/theme'
import { getProfileOutletFromPathname, profileRouteByOutlet } from '../utils/profileRoutes'

const { Content } = Layout

type ProfileLayoutProps = ProfilePageData

export function ProfileLayout(props: ProfileLayoutProps) {
  const { profile, profileStats } = props
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const setActiveOutlet = useProfileOutletStore((state) => state.setActiveOutlet)
  const location = useLocation()
  const navigate = useNavigate()
  const activeOutlet = getProfileOutletFromPathname(location.pathname)

  useEffect(() => {
    setActiveOutlet(activeOutlet)
  }, [activeOutlet, setActiveOutlet])

  return (
    <Layout className="h-screen" style={{ background: colors.bg }}>
      <AppHeader />
      <Content className="h-[calc(100vh-72px)] overflow-hidden" style={{ background: colors.bg }}>
        <main className="mx-auto h-full max-w-[1120px] p-6">
          <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border shadow-sm" style={{ borderColor: colors.border, background: colors.surface }}>
            <div className="shrink-0 border-b p-5" style={{ borderColor: colors.border, background: colors.surfaceMuted }}>
              <ProfileInfoCard profile={profile} stats={profileStats} />
            </div>

            <div className="flex min-h-0 flex-1">
              <ProfileSidebarNav
                activeOutlet={activeOutlet}
                onOutletChange={(outlet) => navigate(profileRouteByOutlet[outlet])}
              />
              <div className="min-h-0 min-w-0 flex-1 overflow-hidden px-5 pt-5" style={{ background: colors.bg }}>
                <Outlet context={props} />
              </div>
            </div>
          </section>
        </main>
      </Content>
    </Layout>
  )
}
