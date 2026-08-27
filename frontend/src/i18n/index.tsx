import { createContext, useContext, type ReactNode } from 'react'
import { useAppSettingsStore } from '../store/useAppSettingsStore'
import { zh, type Dict } from './locales/zh'
import { en } from './locales/en'

type I18nContextValue = {
  t: (key: string, vars?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

const resources: Record<'zh' | 'en', Dict> = { zh, en }

function lookup(dict: unknown, key: string): string {
  const parts = key.split('.')
  let cur: unknown = dict
  for (const part of parts) {
    if (cur && typeof cur === 'object' && part in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[part]
    } else {
      return key
    }
  }
  return typeof cur === 'string' ? cur : key
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (_match, name: string) =>
    name in vars ? String(vars[name]) : `{${name}}`,
  )
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const language = useAppSettingsStore((state) => state.language)

  const t = (key: string, vars?: Record<string, string | number>): string => {
    const dict = language === '英文' ? en : zh
    return interpolate(lookup(resources[language === '英文' ? 'en' : 'zh'], key), vars) || lookup(dict, key)
  }

  return <I18nContext.Provider value={{ t }}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    throw new Error('useI18n must be used within <I18nProvider>')
  }
  return ctx
}
