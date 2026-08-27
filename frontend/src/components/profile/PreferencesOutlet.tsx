import { Alert, Button, Card, Input, Radio, Skeleton, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useState, type Dispatch, type SetStateAction } from 'react'
import type { BudgetPreference, DietaryPreference, PreferenceSettings, TransportPreference, TravelType } from '../../types/profile'
import {
  budgetPreferenceOptions,
  dietaryPreferenceOptions,
  transportPreferenceOptions,
  travelTypeOptions,
} from '../../utils/profileOptions'
import { useI18n } from '../../i18n'

type PreferencesOutletProps = {
  preferences: PreferenceSettings
  setPreferences: Dispatch<SetStateAction<PreferenceSettings>>
  isLoading: boolean
  isSaving: boolean
  error: string | null
  onSave: () => void | Promise<void>
  onDismissError: () => void
}

export function PreferencesOutlet({ preferences, setPreferences, isLoading, isSaving, error, onSave, onDismissError }: PreferencesOutletProps) {
  const [customPreferenceInput, setCustomPreferenceInput] = useState('')
  const hasReachedCustomPreferenceLimit = preferences.customPreferences.length >= 10
  const { t } = useI18n()

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

  function toggleDietaryPreference(value: DietaryPreference) {
    setPreferences((current) => {
      const exists = current.dietaryPreferences.includes(value)

      return {
        ...current,
        dietaryPreferences: exists
          ? current.dietaryPreferences.filter((preference) => preference !== value)
          : [...current.dietaryPreferences, value],
      }
    })
  }

  function removeCustomPreference(value: string) {
    setPreferences((current) => ({
      ...current,
      customPreferences: current.customPreferences.filter((item) => item !== value),
    }))
  }

  return (
    <Card
      className="flex h-full flex-col rounded-2xl border-0 shadow-sm"
      title={t('preferences.title')}
      styles={{ body: { flex: 1, minHeight: 0, overflowY: 'auto', padding: 20 } }}
    >
      <div className="space-y-6">
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 6 }} />
        ) : (
          <>
        <section>
          <div className="mb-3 text-[14px] font-semibold text-slate-900 dark:text-slate-100">{t('preferences.travelType')}</div>
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
          <div className="mb-1 text-[14px] font-semibold text-slate-900 dark:text-slate-100">{t('preferences.dietary')}</div>
          <div className="mb-3 text-[12px] text-slate-400 dark:text-slate-500">{t('preferences.dietaryHint')}</div>
          <div className="flex flex-wrap gap-2">
            {dietaryPreferenceOptions.map((option) => (
              <Button
                key={option}
                type={preferences.dietaryPreferences.includes(option) ? 'primary' : 'default'}
                onClick={() => toggleDietaryPreference(option)}
              >
                {option}
              </Button>
            ))}
          </div>
        </section>

        <section>
          <div className="mb-3 text-[14px] font-semibold text-slate-900 dark:text-slate-100">{t('preferences.budget')}</div>
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
          <div className="mb-3 text-[14px] font-semibold text-slate-900 dark:text-slate-100">{t('preferences.transport')}</div>
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
            <div className="text-[14px] font-semibold text-slate-900 dark:text-slate-100">{t('preferences.custom')}</div>
            <span className="text-[12px] text-slate-400 dark:text-slate-500">
              {t('preferences.customCount', { count: preferences.customPreferences.length })}
            </span>
          </div>
          <div className="flex gap-2">
            <Input
              maxLength={30}
              placeholder={t('preferences.customPlaceholder')}
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
              {t('preferences.add')}
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
          </>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-4 dark:border-slate-800">
          {error ? (
            <Alert
              type="error"
              showIcon
              message={error}
              closable
              onClose={onDismissError}
              className="flex-1"
            />
          ) : (
            <span className="text-[12px] text-slate-400 dark:text-slate-500">
              {isSaving ? t('preferences.saving') : t('preferences.saveHint')}
            </span>
          )}
          <Button type="primary" loading={isSaving} disabled={isLoading} onClick={() => void onSave()}>
            {t('preferences.save')}
          </Button>
        </div>
      </div>
    </Card>
  )
}
