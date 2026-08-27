import type { ReactNode } from 'react'
import { Layout } from 'antd'
import { AppHeader } from '../components/common/AppHeader'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme } from '../utils/theme'

type AppLayoutProps = {
  children: ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)

  return (
    <Layout className="h-screen" style={{ background: colors.bg }}>
      <AppHeader />
      {children}
    </Layout>
  )
}
