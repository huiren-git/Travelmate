import { img } from '../../utils/image'
import type { DataAction, GeneralSettings, PreferenceSettings, UserProfile } from '../../types/profile'

export const userProfile: UserProfile = {
  avatarUrl: img(
    'Friendly modern travel app user avatar portrait, clean background, optimistic blue and coral color accents',
    'square',
  ),
  nickname: '旅行规划师 Ada',
  username: 'ada_travelmate',
  email: 'ada.travelmate@example.com',
  currentCity: '北京',
}

export const initialPreferenceSettings: PreferenceSettings = {
  travelTypes: ['美食', '摄影'],
  budgetPreference: '舒适出行',
  transportPreference: '飞机',
  customPreferences: [],
}

export const initialGeneralSettings: GeneralSettings = {
  theme: '浅色',
  language: '中文',
}

export const dataActions: DataAction[] = [
  {
    id: 'clear-history',
    title: '清空全部历史行程',
    description: '删除当前账号下保存的所有历史行程记录。',
    danger: true,
  },
  {
    id: 'export-history',
    title: '导出全部历史行程数据',
    description: '生成旅行历史数据文件，便于备份或迁移。',
  },
  {
    id: 'reset-cache',
    title: '重置本地缓存',
    description: '清理本地偏好、草稿和临时页面状态。',
  },
]
