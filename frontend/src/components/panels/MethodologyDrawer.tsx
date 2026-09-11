import { useTranslation } from 'react-i18next'

// The one place in the product where methodology/citations live -
// everywhere else shows a plain-language label instead of a citation
// string. Opened on demand, never shown inline in the main interface.
export function MethodologyDrawer({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center p-4"
      style={{ background: 'var(--surface-overlay)' }}
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-[480px] overflow-y-auto rounded-lg p-5"
        style={{ background: 'var(--surface-card)', boxShadow: 'var(--shadow-lg)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('methodology.title')}</h2>
          <button onClick={onClose} className="rounded p-1 transition-colors hover:bg-[var(--surface-sunken)]" aria-label={t('common.close')}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 3l10 10M13 3L3 13" stroke="var(--text-tertiary)" strokeWidth="1.6" strokeLinecap="round" /></svg>
          </button>
        </div>

        <div className="mt-3 space-y-3 text-[13px] leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          <p>{t('methodology.heatStress')}</p>
          <p>{t('methodology.mortality')}</p>
          <p>{t('methodology.confidence')}</p>
          <p>{t('methodology.wardScope')}</p>
        </div>

        <div className="mt-4 border-t pt-3" style={{ borderColor: 'var(--border-subtle)' }}>
          <p className="text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>{t('methodology.sources')}</p>
          <ul className="mt-1.5 space-y-1.5 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
            <li>{t('methodology.sourceAllCause')}</li>
            <li>{t('methodology.sourceHeatstroke')}</li>
            <li>{t('methodology.sourceOccupational')}</li>
            <li>{t('methodology.sourceEms')}</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
