import type { ThemePreference } from '../types/profile'

export type TravelmateTheme = {
  primary: string
  primary2: string
  bg: string
  surface: string
  surfaceMuted: string
  accent: string
  accentHover: string
  textPrimary: string
  textSecondary: string
  border: string
}

export const travelmateThemeLight: TravelmateTheme = {
  primary: '#0071EB',
  primary2: '#1B8CD1',
  bg: '#f8f9fa',
  surface: '#ffffff',
  surfaceMuted: '#f1f5f9',
  accent: '#FF6F61',
  accentHover: '#ff5c4f',
  textPrimary: '#0f172a',
  textSecondary: '#64748b',
  border: '#e2e8f0',
}

export const travelmateThemeDark: TravelmateTheme = {
  primary: '#3B9EFF',
  primary2: '#5AB4E8',
  bg: '#0b1120',
  surface: '#111827',
  surfaceMuted: '#0f172a',
  accent: '#FF8A7A',
  accentHover: '#ff7a68',
  textPrimary: '#e5e7eb',
  textSecondary: '#94a3b8',
  border: '#1f2a3a',
}

// 兼容旧引用：默认仍指向浅色
export const travelmateTheme: TravelmateTheme = travelmateThemeLight

export function resolveTheme(pref: ThemePreference): 'light' | 'dark' {
  if (pref === '跟随系统') {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return 'light'
  }
  return pref === '深色' ? 'dark' : 'light'
}

export function getTravelmateTheme(pref: ThemePreference): TravelmateTheme {
  return resolveTheme(pref) === 'dark' ? travelmateThemeDark : travelmateThemeLight
}
