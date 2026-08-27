export type ProfileOutletKey = 'preferences' | 'history' | 'settings'

export type TravelType = '美食' | '摄影' | '自然风光' | '人文古迹'

export type BudgetPreference = '经济实惠' | '舒适出行' | '奢华体验'

export type TransportPreference = '火车' | '飞机' | '自驾'

export type DietaryPreference = '爱吃辣' | '爱吃甜' | '当地特色' | '清淡饮食' | '素食优先' | '海鲜偏好'

export type ThemePreference = '浅色' | '深色' | '跟随系统'

export type LanguagePreference = '中文' | '英文'

export type UserProfile = {
  avatarUrl: string
  nickname: string
  username: string
  email: string
  currentCity: string
}

export type PreferenceSettings = {
  travelTypes: TravelType[]
  budgetPreference: BudgetPreference
  transportPreference: TransportPreference
  dietaryPreferences: DietaryPreference[]
  customPreferences: string[]
}

export type GeneralSettings = {
  theme: ThemePreference
  language: LanguagePreference
}

export type ProfileTravelStats = {
  tripCount: number
  visitedCityCount: number
  totalDays: number
}

export type DataAction = {
  id: string
  title: string
  description: string
  danger?: boolean
}
