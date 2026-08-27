import type {
  BudgetPreference,
  DietaryPreference,
  LanguagePreference,
  ThemePreference,
  TransportPreference,
  TravelType,
} from '../types/profile'

export const travelTypeOptions: TravelType[] = ['美食', '摄影', '自然风光', '人文古迹']

export const budgetPreferenceOptions: BudgetPreference[] = ['经济实惠', '舒适出行', '奢华体验']

export const transportPreferenceOptions: TransportPreference[] = ['火车', '飞机', '自驾']

export const dietaryPreferenceOptions: DietaryPreference[] = ['爱吃辣', '爱吃甜', '当地特色', '清淡饮食', '素食优先', '海鲜偏好']

export const themePreferenceOptions: ThemePreference[] = ['浅色', '深色', '跟随系统']

export const languagePreferenceOptions: LanguagePreference[] = ['中文', '英文']
