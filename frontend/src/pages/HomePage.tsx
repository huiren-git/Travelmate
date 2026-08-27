import type { ReactNode } from 'react'
import {
  CompassOutlined,
  DashboardOutlined,
  MessageOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import { Button, Card, Layout, Tag, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { AppHeader } from '../components/common/AppHeader'
import { img } from '../utils/image'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { getTravelmateTheme, resolveTheme } from '../utils/theme.tsx'
import { useI18n } from '../i18n'

const { Content } = Layout

type FeatureCard = {
  title: string
  slogan: string
  icon: ReactNode
  enabled: boolean
  path?: string
}

const bannerImage = img(
  'bright realistic travel planning scene with blue sky, suitcase, map, phone itinerary app, clean modern optimistic style',
  'landscape_16_9',
)

export default function HomePage() {
  const navigate = useNavigate()
  const [messageApi, contextHolder] = message.useMessage()
  const theme = useAppSettingsStore((state) => state.theme)
  const colors = getTravelmateTheme(theme)
  const { t } = useI18n()

  const overlay = resolveTheme(theme) === 'dark' ? 'rgba(15, 23, 42, 0.82)' : 'rgba(255, 255, 255, 0.82)'

  const featureCards: FeatureCard[] = [
    {
      title: t('home.featureChat.title'),
      slogan: t('home.featureChat.slogan'),
      icon: <MessageOutlined />,
      enabled: true,
    },
    {
      title: t('home.featureReference.title'),
      slogan: t('home.featureReference.slogan'),
      icon: <CompassOutlined />,
      enabled: false,
    },
    {
      title: t('home.featureEval.title'),
      slogan: t('home.featureEval.slogan'),
      icon: <DashboardOutlined />,
      enabled: true,
      path: '/traces',
    },
  ]

  const handleComingSoon = (title: string) => {
    void messageApi.info(t('home.comingSoon', { title }))
  }

  return (
    <Layout className="min-h-screen" style={{ backgroundColor: colors.bg }}>
      {contextHolder}
      <AppHeader />

      <Content className="px-5 py-6 sm:px-8 lg:px-12">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-6">
          <section className="relative min-h-[360px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <img src={bannerImage} alt="" className="absolute inset-0 h-full w-full object-cover" />
            <div className="absolute inset-0" style={{ backgroundColor: overlay }} />

            <div className="relative flex min-h-[360px] flex-col justify-between p-6 sm:p-8 lg:p-10">
              <div>
                <div className="mb-3 flex flex-wrap items-center gap-3 sm:gap-4">
                  <div className="inline-flex items-center gap-3">
                    <span
                      className="flex h-11 w-11 items-center justify-center rounded-lg text-[20px] text-white shadow-sm"
                      style={{ backgroundColor: colors.primary }}
                    >
                      <RocketOutlined />
                    </span>
                    <h1 className="m-0 text-[42px] font-bold leading-tight text-slate-950 dark:text-slate-50 sm:text-[54px]">
                      Travelmate
                    </h1>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Tag className="m-0 rounded-full px-3.5 py-1 text-[13px]" color="blue">
                      {t('home.tagMultiAgent')}
                    </Tag>
                    <Tag
                      className="m-0 rounded-full px-3.5 py-1 text-[13px]"
                      style={{ color: colors.accent, borderColor: '#ffd7d2', backgroundColor: '#fff1ef' }}
                    >
                      {t('home.tagObservability')}
                    </Tag>
                  </div>
                </div>

                <p className="m-0 text-[22px] font-medium text-slate-700 dark:text-slate-200 sm:text-[26px]">
                  {t('home.slogan')}
                </p>
              </div>

              <div className="mt-10 flex flex-wrap gap-3">
                <Button
                  type="primary"
                  size="large"
                  icon={<MessageOutlined />}
                  onClick={() => navigate('/chat')}
                  style={{
                    backgroundColor: colors.accent,
                    borderColor: colors.accent,
                    boxShadow: '0 12px 26px rgba(255, 111, 97, 0.24)',
                  }}
                >
                  {t('home.startChat')}
                </Button>
                <Button size="large" icon={<CompassOutlined />} onClick={() => handleComingSoon(t('home.attractions'))}>
                  {t('home.attractions')}
                </Button>
                <Button size="large" icon={<DashboardOutlined />} onClick={() => navigate('/traces')}>
                  {t('home.evalConsole')}
                </Button>
              </div>
            </div>
          </section>

          <section className="grid gap-5 lg:grid-cols-3">
            {featureCards.map((card) => (
              <Card key={card.title} className="rounded-lg border-slate-200 shadow-sm dark:border-slate-800" styles={{ body: { padding: 24 } }}>
                <div className="flex min-h-[220px] flex-col">
                  <div
                    className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg text-[20px]"
                    style={{
                      color: card.enabled ? colors.primary : colors.textSecondary,
                      backgroundColor: card.enabled ? '#eaf4ff' : colors.surfaceMuted,
                    }}
                  >
                    {card.icon}
                  </div>
                  <h2 className="m-0 text-[22px] font-semibold text-slate-950 dark:text-slate-50">{card.title}</h2>
                  <p className="mt-3 whitespace-pre-line text-[15px] leading-7 text-slate-600 dark:text-slate-300">{card.slogan}</p>
                  <div className="mt-auto flex justify-end pt-5">
                    <Button
                      type={card.enabled ? 'primary' : 'default'}
                      className="h-10 rounded-xl px-5 text-[14px] font-semibold"
                      onClick={() => {
                        if (card.enabled) {
                          navigate(card.path ?? '/chat')
                          return
                        }
                        handleComingSoon(card.title)
                      }}
                      style={
                        card.enabled
                          ? {
                              backgroundColor: colors.accent,
                              borderColor: colors.accent,
                            }
                          : undefined
                      }
                    >
                      {t('home.enter')}
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </section>
        </div>
      </Content>
    </Layout>
  )
}
