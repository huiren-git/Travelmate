import { Button, Card, Input, Radio, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useState, type Dispatch, type SetStateAction } from 'react'
import type { BudgetPreference, PreferenceSettings, TransportPreference, TravelType } from '../../types/profile'
import { budgetPreferenceOptions, transportPreferenceOptions, travelTypeOptions } from '../../utils/profileOptions'

type PreferencesOutletProps = {
  preferences: PreferenceSettings
  setPreferences: Dispatch<SetStateAction<PreferenceSettings>>
}

export function PreferencesOutlet({ preferences, setPreferences }: PreferencesOutletProps) {
  const [customPreferenceInput, setCustomPreferenceInput] = useState('')
  const hasReachedCustomPreferenceLimit = preferences.customPreferences.length >= 10

  function toggleTravelType(value: TravelType) {
    setPreferences((current) => {
      const exists = current.travelTypes.includes(value)
      return {
        ...current,
        travelTypes: exists
          ? current.travelTypes.filter((travelType) => travelType !== value)
          : [...current.travelTypes, value],
      }
    })
  }

  function addCustomPreference() {
    const value = customPreferenceInput.trim()

    if (!value || hasReachedCustomPreferenceLimit || preferences.customPreferences.includes(value)) {
      return
    }

    setPreferences((current) => ({
      ...current,
      customPreferences: [...current.customPreferences, value],
    }))
    setCustomPreferenceInput('')
  }

  function removeCustomPreference(value: string) {
    setPreferences((current) => ({
      ...current,
      customPreferences: current.customPreferences.filter((item) => item !== value),
    }))
  }

  return (
    <Card className="rounded-2xl border-0 shadow-sm" title="我的偏好" styles={{ body: { padding: 20 } }}>
      <div className="space-y-6">
        <section>
          <div className="mb-3 text-[14px] font-semibold text-slate-900">旅行类型选择</div>
          <div className="flex flex-wrap gap-2">
            {travelTypeOptions.map((option) => (
              <Button
                key={option}
                type={preferences.travelTypes.includes(option) ? 'primary' : 'default'}
                onClick={() => toggleTravelType(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-3 text-[14px] font-semibold text-slate-900">预算偏好</div>
          <Radio.Group
            value={preferences.budgetPreference}
            onChange={(event) =>
              setPreferences((current) => ({
                ...current,
                budgetPreference: event.target.value as BudgetPreference,
              }))
            }
          >
            {budgetPreferenceOptions.map((option) => (
              <Radio.Button key={option} value={option}>
                {option}
              </Radio.Button>
            ))}
          </Radio.Group>
        </section>

        <section>
          <div className="mb-3 text-[14px] font-semibold text-slate-900">出行交通方式</div>
          <Radio.Group
            value={preferences.transportPreference}
            onChange={(event) =>
              setPreferences((current) => ({
                ...current,
                transportPreference: event.target.value as TransportPreference,
              }))
            }
          >
            {transportPreferenceOptions.map((option) => (
              <Radio.Button key={option} value={option}>
                {option}
              </Radio.Button>
            ))}
          </Radio.Group>
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between gap-4">
            <div className="text-[14px] font-semibold text-slate-900">自定义偏好</div>
            <span className="text-[12px] text-slate-400">{preferences.customPreferences.length}/10</span>
          </div>
          <div className="flex gap-2">
            <Input
              maxLength={30}
              placeholder="输入一条偏好，最多 30 个字"
              value={customPreferenceInput}
              disabled={hasReachedCustomPreferenceLimit}
              onChange={(event) => setCustomPreferenceInput(event.target.value)}
              onPressEnter={addCustomPreference}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              disabled={!customPreferenceInput.trim() || hasReachedCustomPreferenceLimit}
              onClick={addCustomPreference}
            >
              添加
            </Button>
          </div>
          {preferences.customPreferences.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {preferences.customPreferences.map((preference) => (
                <Tag key={preference} closable onClose={() => removeCustomPreference(preference)}>
                  {preference}
                </Tag>
              ))}
            </div>
          )}
        </section>

        <div className="flex justify-end border-t border-slate-100 pt-4">
          <Button type="primary">保存</Button>
        </div>
      </div>
    </Card>
  )
}
