import { ConfigProvider } from 'antd'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import TravelmateDashboardPage from '../pages/ChatPage'
import HistoryPage from '../pages/HistoryPage'
import ProfilePage from '../pages/ProfilePage'
import SettingsPage from '../pages/SettingsPage'
import { ProfileOutletPanel } from '../components/profile/ProfileOutletPanel'

function withAppLayout(page: React.ReactNode) {
  return <AppLayout>{page}</AppLayout>
}

export default function AppRouter() {
  return (
    <ConfigProvider
      theme={{
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
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={withAppLayout(<TravelmateDashboardPage />)} />
          <Route path="/history" element={withAppLayout(<HistoryPage />)} />
          <Route path="/profile" element={<ProfilePage />}>
            <Route index element={<Navigate to="preferences" replace />} />
            <Route path="preferences" element={<ProfileOutletPanel outletKey="preferences" />} />
            <Route path="history" element={<ProfileOutletPanel outletKey="history" />} />
            <Route path="settings" element={<ProfileOutletPanel outletKey="settings" />} />
          </Route>
          <Route path="/settings" element={withAppLayout(<SettingsPage />)} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
