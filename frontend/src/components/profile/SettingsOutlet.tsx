import { Button, Card, List, Modal, Radio, Select, Space, message } from 'antd'
import { useEffect, useState } from 'react'
import type { LanguagePreference, ThemePreference, UserProfile } from '../../types/profile'
import type { ExportFormat } from '../../hooks/useProfilePageData'
import { dataActions } from '../../assets/profile/profileData'
import { getProfileActionConfirmContent, getProfileActionConfirmTitle } from '../../utils/profileActions'
import { languagePreferenceOptions, themePreferenceOptions } from '../../utils/profileOptions'
import { useAppSettingsStore } from '../../store/useAppSettingsStore'
import { useProfileOutletStore } from '../../store/useProfileOutletStore'
import { useHistoryOutletStore } from '../../store/useHistoryOutletStore'
import { useI18n } from '../../i18n'

type SettingsOutletProps = {
  profile: UserProfile
  onClearHistory: () => Promise<number>
  onExportHistory: (format: ExportFormat) => Promise<number>
}

// 自管选中状态，避免 Modal.confirm 的内容不被 React 重渲染导致单选框不更新。
function ExportFormatPicker({ onChange }: { onChange: (value: ExportFormat) => void }) {
  const [format, setFormat] = useState<ExportFormat>('json')

  useEffect(() => {
    onChange(format)
  }, [format, onChange])

  return (
    <div className="space-y-3">
      <div className="text-[13px] text-slate-600 dark:text-slate-300">请选择导出文件格式：</div>
      <Radio.Group value={format} onChange={(event) => setFormat(event.target.value as ExportFormat)}>
        <Space direction="vertical">
          <Radio value="json">JSON（推荐 · 完整备份 / 可重新导入）</Radio>
          <Radio value="excel">Excel .xlsx（便于在 Excel / WPS 中查看与统计）</Radio>
        </Space>
      </Radio.Group>
    </div>
  )
}

const themeLabelMap: Record<ThemePreference, string> = {
  浅色: 'settings.themeOptions.light',
  深色: 'settings.themeOptions.dark',
  跟随系统: 'settings.themeOptions.system',
}

const languageLabelMap: Record<LanguagePreference, string> = {
  中文: 'settings.languageOptions.zh',
  英文: 'settings.languageOptions.en',
}

export function SettingsOutlet({ profile, onClearHistory, onExportHistory }: SettingsOutletProps) {
  const theme = useAppSettingsStore((state) => state.theme)
  const language = useAppSettingsStore((state) => state.language)
  const setTheme = useAppSettingsStore((state) => state.setTheme)
  const setLanguage = useAppSettingsStore((state) => state.setLanguage)
  const { t } = useI18n()
  const [messageApi, contextHolder] = message.useMessage()
  const [selectedExportFormat, setSelectedExportFormat] = useState<ExportFormat>('json')

  function confirmDataAction(actionId: string) {
    const action = dataActions.find((item) => item.id === actionId)
    if (!action) return

    // 导出：在 Modal 内嵌格式选择，再按所选格式现场拉取并下载。
    if (action.id === 'export-history') {
      setSelectedExportFormat('json')
      Modal.confirm({
        title: action.title,
        content: <ExportFormatPicker onChange={setSelectedExportFormat} />,
        okText: t('settings.execute'),
        cancelText: t('settings.cancel'),
        onOk: async () => {
          try {
            const count = await onExportHistory(selectedExportFormat)
            if (count > 0) {
              messageApi.success(t('settings.exportSuccess', { count }))
            } else {
              messageApi.info(t('settings.exportEmpty'))
            }
          } catch (error) {
            messageApi.error(error instanceof Error ? error.message : t('settings.exportFailed'))
            throw error
          }
        },
      })
      return
    }

    const isClearHistory = action.id === 'clear-history'
    const isResetCache = action.id === 'reset-cache'

    Modal.confirm({
      title: getProfileActionConfirmTitle(action),
      content: getProfileActionConfirmContent(action),
      okText: isClearHistory ? t('settings.clear') : t('settings.confirmOk'),
      okButtonProps: action.danger ? { danger: true } : undefined,
      cancelText: t('settings.cancel'),
      onOk: isClearHistory
        ? async () => {
            try {
              const deletedCount = await onClearHistory()
              if (deletedCount > 0) {
                messageApi.success(t('settings.clearSuccess', { count: deletedCount }))
              } else {
                messageApi.info(t('settings.clearEmpty'))
              }
            } catch (error) {
              messageApi.error(error instanceof Error ? error.message : t('settings.clearFailed'))
              throw error
            }
          }
        : isResetCache
        ? () => {
            useAppSettingsStore.getState().resetLocalCache()
            useProfileOutletStore.getState().reset()
            useHistoryOutletStore.getState().reset()
            messageApi.success('本地缓存已重置')
            setTimeout(() => window.location.reload(), 400)
          }
        : undefined,
    })
  }

  return (
    <>
      {contextHolder}
      <Card
        className="flex h-full flex-col rounded-2xl border-0 shadow-sm"
        title={t('settings.title')}
        styles={{ body: { flex: 1, minHeight: 0, overflowY: 'auto', padding: 20 } }}
      >
        <div className="space-y-7">
          <section>
            <div className="mb-4 text-[15px] font-bold text-slate-900 dark:text-slate-100">{t('settings.general')}</div>
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <div className="mb-2 text-[13px] font-semibold text-slate-600 dark:text-slate-300">{t('settings.theme')}</div>
                <Radio.Group
                  value={theme}
                  onChange={(event) => setTheme(event.target.value as ThemePreference)}
                >
                  {themePreferenceOptions.map((option) => (
                    <Radio.Button key={option} value={option}>
                      {t(themeLabelMap[option])}
                    </Radio.Button>
                  ))}
                </Radio.Group>
              </div>

              <div>
                <div className="mb-2 text-[13px] font-semibold text-slate-600 dark:text-slate-300">{t('settings.language')}</div>
                <Select
                  className="w-[180px]"
                  value={language}
                  options={languagePreferenceOptions.map((option) => ({
                    label: t(languageLabelMap[option]),
                    value: option,
                  }))}
                  onChange={(value) => setLanguage(value as LanguagePreference)}
                />
              </div>
            </div>
          </section>

          <section>
            <div className="mb-4 text-[15px] font-bold text-slate-900 dark:text-slate-100">{t('settings.account')}</div>
            <div className="flex items-center justify-between rounded-xl bg-slate-50 p-4 dark:bg-slate-800/60">
              <div>
                <div className="text-[12px] text-slate-400">{t('settings.username')}</div>
                <div className="mt-1 text-[15px] font-semibold text-slate-900 dark:text-slate-100">@{profile.username}</div>
              </div>
              <Button danger onClick={() => confirmDataAction('logout-account')}>
                {t('settings.logout')}
              </Button>
            </div>
          </section>

          <section>
            <div className="mb-4 text-[15px] font-bold text-slate-900 dark:text-slate-100">{t('settings.data')}</div>
            <List
              bordered={false}
              dataSource={dataActions}
              renderItem={(action) => (
                <List.Item
                  className="rounded-xl px-4"
                  actions={[
                    <Button key={action.id} danger={action.danger} onClick={() => confirmDataAction(action.id)}>
                      {t('settings.execute')}
                    </Button>,
                  ]}
                >
                  <List.Item.Meta title={action.title} description={action.description} />
                </List.Item>
              )}
            />
          </section>
        </div>
      </Card>
    </>
  )
}
