import { useI18n } from '../../i18n'

export function NewTripEmptyState() {
  const { t } = useI18n()
  return (
    <section className="flex min-h-[45vh] items-start justify-center pt-[18vh] text-center">
      <div className="max-w-[680px] px-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{t('chat.greeting')}</h1>
        <p className="mt-4 text-[15px] leading-7 text-slate-500 dark:text-slate-400">{t('chat.greetingDesc')}</p>
      </div>
    </section>
  )
}
