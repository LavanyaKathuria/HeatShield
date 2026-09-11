import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { code: 'en', label: 'EN' },
  { code: 'hi', label: 'हि' },
  { code: 'gu', label: 'ગુ' },
]

export function LanguageSwitcher() {
  const { i18n } = useTranslation()

  return (
    <div className="flex items-center gap-0.5 rounded-md border p-0.5" style={{ borderColor: 'var(--border-subtle)' }}>
      {LANGUAGES.map((lang) => {
        const active = i18n.language === lang.code
        return (
          <button
            key={lang.code}
            onClick={() => i18n.changeLanguage(lang.code)}
            className="rounded px-2 py-1 text-[12px] font-medium transition-colors"
            style={
              active
                ? { background: 'var(--accent-soft)', color: 'var(--accent)' }
                : { color: 'var(--text-tertiary)' }
            }
          >
            {lang.label}
          </button>
        )
      })}
    </div>
  )
}
