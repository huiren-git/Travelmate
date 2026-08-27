import { initialPreferenceSettings } from '../assets/profile/profileData'
import type { PreferenceItem, PreferenceItemInput } from '../api/preferences'
import type {
  BudgetPreference,
  DietaryPreference,
  PreferenceSettings,
  TransportPreference,
  TravelType,
} from '../types/profile'
import {
  budgetPreferenceOptions,
  dietaryPreferenceOptions,
  transportPreferenceOptions,
  travelTypeOptions,
} from './profileOptions'

/**
 * 前端 PreferenceSettings → 后端 {category, content}[] 映射：
 * - travelTypes      → interest
 * - budgetPreference → budget（单条）
 * - transportPreference → transport（单条）
 * - dietaryPreferences → diet（每条一条）
 * - customPreferences → interest（每条一条）
 */
export function preferenceSettingsToItems(settings: PreferenceSettings): PreferenceItemInput[] {
  const items: PreferenceItemInput[] = []

  for (const travelType of settings.travelTypes) {
    items.push({ category: 'interest', content: travelType })
  }
  if (settings.budgetPreference) {
    items.push({ category: 'budget', content: settings.budgetPreference })
  }
  if (settings.transportPreference) {
    items.push({ category: 'transport', content: settings.transportPreference })
  }
  for (const dietary of settings.dietaryPreferences) {
    items.push({ category: 'diet', content: dietary })
  }
  for (const custom of settings.customPreferences) {
    items.push({ category: 'interest', content: custom })
  }

  return items
}

/**
 * 后端 PreferenceItem[] → 前端 PreferenceSettings 重建：
 * 仅采用 source=manual 且 is_active 的项；推断偏好不回填表单（仍由后端 RAG 使用）。
 * - budget    命中 budgetPreferenceOptions → budgetPreference
 * - transport 命中 transportPreferenceOptions → transportPreference
 * - diet      命中 dietaryPreferenceOptions → dietaryPreferences
 * - interest  命中 travelTypeOptions → travelTypes；否则 → customPreferences
 * 缺失的枚举字段回退到 initialPreferenceSettings 默认值。
 */
export function itemsToPreferenceSettings(items: PreferenceItem[]): PreferenceSettings {
  const manual = items.filter((item) => item.source === 'manual' && item.is_active)

  const travelTypes: TravelType[] = []
  const customPreferences: string[] = []
  const dietaryPreferences: DietaryPreference[] = []
  let budgetPreference: BudgetPreference | undefined
  let transportPreference: TransportPreference | undefined

  for (const item of manual) {
    if (
      item.category === 'budget' &&
      budgetPreferenceOptions.includes(item.content as BudgetPreference)
    ) {
      budgetPreference = item.content as BudgetPreference
    } else if (
      item.category === 'transport' &&
      transportPreferenceOptions.includes(item.content as TransportPreference)
    ) {
      transportPreference = item.content as TransportPreference
    } else if (
      item.category === 'diet' &&
      dietaryPreferenceOptions.includes(item.content as DietaryPreference)
    ) {
      dietaryPreferences.push(item.content as DietaryPreference)
    } else if (item.category === 'interest') {
      if (travelTypeOptions.includes(item.content as TravelType)) {
        travelTypes.push(item.content as TravelType)
      } else {
        customPreferences.push(item.content)
      }
    }
  }

  return {
    travelTypes,
    budgetPreference: budgetPreference ?? initialPreferenceSettings.budgetPreference,
    transportPreference: transportPreference ?? initialPreferenceSettings.transportPreference,
    dietaryPreferences,
    customPreferences,
  }
}
