import { useTranslation } from 'react-i18next'

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <div className="flex h-full min-h-[120px] w-full flex-col items-center justify-center gap-3" style={{ color: 'var(--text-tertiary)' }}>
      <div
        className="h-6 w-6 animate-spin rounded-full border-2"
        style={{ borderColor: 'var(--border-default)', borderTopColor: 'var(--accent)' }}
      />
      <span className="text-[13px]">{label ?? t('common.loading')}</span>
    </div>
  )
}

// A content-shaped placeholder for first paint - reads as "the product
// is loading real data," not a spinner floating in empty space.
export function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} />
}
