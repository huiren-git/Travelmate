import { Button, Card, List, Modal, Radio, Select } from 'antd'
import type { Dispatch, SetStateAction } from 'react'
import { dataActions } from '../../assets/profile/profileData'
import type { GeneralSettings, LanguagePreference, ThemePreference, UserProfile } from '../../types/profile'
import { getProfileActionConfirmContent, getProfileActionConfirmTitle } from '../../utils/profileActions'
import { languagePreferenceOptions, themePreferenceOptions } from '../../utils/profileOptions'

type SettingsOutletProps = {
  profile: UserProfile
  settings: GeneralSettings
  setSettings: Dispatch<SetStateAction<GeneralSettings>>
}

export function SettingsOutlet({ profile, settings, setSettings }: SettingsOutletProps) {
  function confirmDataAction(actionId: string) {
    const action = dataActions.find((item) => item.id === actionId)
    if (!action) return

    Modal.confirm({
      title: getProfileActionConfirmTitle(action),
      content: getProfileActionConfirmContent(action),
      okText: action.danger ? '确认删除' : '确认',
      okButtonProps: action.danger ? { danger: true } : undefined,
      cancelText: '取消',
    })
  }

  return (
    <Card className="rounded-2xl border-0 shadow-sm" title="设置" styles={{ body: { padding: 20 } }}>
      <div className="space-y-7">
        <section>
          <div className="mb-4 text-[15px] font-bold text-slate-900">通用设置</div>
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <div className="mb-2 text-[13px] font-semibold text-slate-600">主题</div>
              <Radio.Group
                value={settings.theme}
                onChange={(event) =>
                  setSettings((current) => ({
                    ...current,
                    theme: event.target.value as ThemePreference,
                  }))
                }
              >
                {themePreferenceOptions.map((option) => (
                  <Radio.Button key={option} value={option}>
                    {option}
                  </Radio.Button>
                ))}
              </Radio.Group>
            </div>

            <div>
              <div className="mb-2 text-[13px] font-semibold text-slate-600">语言</div>
              <Select
                className="w-[180px]"
                value={settings.language}
                options={languagePreferenceOptions.map((option) => ({ label: option, value: option }))}
                onChange={(value) =>
                  setSettings((current) => ({
                    ...current,
                    language: value as LanguagePreference,
                  }))
                }
              />
            </div>
          </div>
        </section>

        <section>
          <div className="mb-4 text-[15px] font-bold text-slate-900">账号管理</div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 p-4">
            <div>
              <div className="text-[12px] text-slate-400">用户名</div>
              <div className="mt-1 text-[15px] font-semibold text-slate-900">@{profile.username}</div>
            </div>
            <Button danger onClick={() => confirmDataAction('logout-account')}>
              注销账号
            </Button>
          </div>
        </section>

        <section>
          <div className="mb-4 text-[15px] font-bold text-slate-900">数据管理</div>
          <List
            bordered={false}
            dataSource={dataActions}
            renderItem={(action) => (
              <List.Item
                className="rounded-xl px-4"
                actions={[
                  <Button key={action.id} danger={action.danger} onClick={() => confirmDataAction(action.id)}>
                    执行
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
  )
}
