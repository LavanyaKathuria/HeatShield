import { useTranslation } from 'react-i18next'

// Every caller passes a translated, human-readable message - never a
// raw error object, status code, or technical string. Falls back to a
// generic, still-polished message if none is given.
export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  const { t } = useTranslation()
  return (
    <div
      className="flex h-full min-h-[120px] w-full flex-col items-center justify-center gap-3 rounded-lg p-5 text-center"
      style={{ background: 'var(--risk-danger-soft)' }}
    >
      <span className="text-[13px]" style={{ color: 'var(--risk-danger)' }}>
        {message ?? t('common.genericError')}
      </span>
      {onRetry && (
        <button onClick={onRetry} className="btn btn-secondary !py-1.5 !text-[13px]">
          {t('common.retry')}
        </button>
      )}
    </div>
  )
}
