import type { ReactNode } from 'react'
import { Layout } from 'antd'
import { AppHeader } from '../components/common/AppHeader'
import { travelmateTheme } from '../utils/theme.tsx'

type AppLayoutProps = {
  children: ReactNode
}

export function AppLayout({ children }: AppLayoutProps) {
  return (
    <Layout className="h-screen" style={{ background: travelmateTheme.bg }}>
      <AppHeader colors={travelmateTheme} />
      {children}
    </Layout>
  )
}
