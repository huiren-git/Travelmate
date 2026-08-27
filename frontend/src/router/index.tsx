import { useEffect } from 'react'
import { ConfigProvider, theme as antdTheme } from 'antd'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { resolveTheme } from '../utils/theme'
import TravelmateDashboardPage from '../pages/ChatPage'
import HomePage from '../pages/HomePage'
import ReferenceTripsPage from '../pages/ReferenceTripsPage'
import HistoryPage from '../pages/HistoryPage'
import ProfilePage from '../pages/ProfilePage'
import TraceDetailPage from '../pages/TraceDetailPage'
import TracesPage from '../pages/TracesPage'
import { ProfileOutletPanel } from '../components/profile/ProfileOutletPanel'

function withAppLayout(page: React.ReactNode) {
  return <AppLayout>{page}</AppLayout>
}

export default function AppRouter() {
  const theme = useAppSettingsStore((state) => state.theme)
  const language = useAppSettingsStore((state) => state.language)
  const resolved = resolveTheme(theme)

  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', resolved === 'dark')
    root.lang = language === '英文' ? 'en' : 'zh-CN'
  }, [resolved, language])

  return (
    <ConfigProvider
      theme={{
        algorithm: resolved === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#0071EB',
          colorInfo: '#0071EB',
          colorLink: '#0071EB',
          borderRadiusLG: 16,
          borderRadius: 12,
        },
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/chat" element={withAppLayout(<TravelmateDashboardPage />)} />
          <Route path="/reference" element={withAppLayout(<ReferenceTripsPage />)} />
          <Route path="/history" element={withAppLayout(<HistoryPage />)} />
          <Route path="/traces" element={withAppLayout(<TracesPage />)} />
          <Route path="/traces/:id" element={withAppLayout(<TraceDetailPage />)} />
          <Route path="/profile" element={<ProfilePage />}>
            <Route index element={<Navigate to="preferences" replace />} />
            <Route path="preferences" element={<ProfileOutletPanel outletKey="preferences" />} />
            <Route path="history" element={<ProfileOutletPanel outletKey="history" />} />
            <Route path="settings" element={<ProfileOutletPanel outletKey="settings" />} />
          </Route>
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
