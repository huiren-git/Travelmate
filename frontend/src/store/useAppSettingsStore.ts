import { create } from 'zustand'
import type { LanguagePreference, ThemePreference } from '../types/profile'

type AppSettingsState = {
  theme: ThemePreference
  language: LanguagePreference
  setTheme: (theme: ThemePreference) => void
  setLanguage: (language: LanguagePreference) => void
  resetLocalCache: () => void
}

const STORAGE_KEY = 'travelmate-app-settings'

function load(): { theme: ThemePreference; language: LanguagePreference } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<{ theme: ThemePreference; language: LanguagePreference }>
      return {
        theme: parsed.theme ?? '浅色',
        language: parsed.language ?? '中文',
      }
    }
  } catch {
    // 解析失败时回退默认值
  }
  return { theme: '浅色', language: '中文' }
}

const initial = load()

function persist(theme: ThemePreference, language: LanguagePreference) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme, language }))
  } catch {
    // localStorage 不可用时静默忽略
  }
}

export const useAppSettingsStore = create<AppSettingsState>((set) => ({
  theme: initial.theme,
  language: initial.language,
  setTheme: (theme) => {
    persist(theme, useAppSettingsStore.getState().language)
    set({ theme })
  },
  setLanguage: (language) => {
    persist(useAppSettingsStore.getState().theme, language)
    set({ language })
  },
  resetLocalCache: () => {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // localStorage 不可用时静默忽略
    }
    set({ theme: '浅色', language: '中文' })
  },
}))
