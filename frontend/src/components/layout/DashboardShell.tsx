import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { LocationControl } from '@/components/layout/LocationControl'
import { LanguageSwitcher } from '@/components/layout/LanguageSwitcher'
import { ProfileMenu } from '@/components/layout/ProfileMenu'
import { HistoricalReplayControl } from '@/components/layout/HistoricalReplayControl'
import { useMapStore } from '@/store/useMapStore'

interface DashboardShellProps {
  children: ReactNode
  /** Rendered between the location control and language switcher - the
   * map-mode segmented control on map-first screens, omitted elsewhere. */
  navCenter?: ReactNode
  /** Screens that are their own full-bleed layout (the map stage) render
   * children directly with no scroll container; others get one. */
  fullBleed?: boolean
}

export function DashboardShell({ children, navCenter, fullBleed }: DashboardShellProps) {
  const { t } = useTranslation()
  const source = useMapStore((s) => s.source)

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--surface-page)' }}>
      <header
        className="z-20 flex min-h-14 flex-wrap flex-shrink-0 items-center gap-3 border-b px-4 py-2"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--surface-card)' }}
      >
        <div className="flex items-center gap-2">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style={{ color: 'var(--accent)' }}>
            <path d="M12 2C12 2 6 10 6 15a6 6 0 0 0 12 0c0-5-6-13-6-13Z" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" />
          </svg>
          <span className="hidden text-[15px] font-semibold sm:inline" style={{ color: 'var(--text-primary)' }}>
            {t('app.name')}
          </span>
        </div>

        <LocationControl />

        <div className="flex-1" />

        <HistoricalReplayControl />
        {navCenter}

        <LanguageSwitcher />
        <ProfileMenu />
      </header>
      {source === 'may_2024' && <div className="shrink-0 border-b px-4 py-2 text-[12px]" style={{ background: 'var(--risk-warning-soft)', color: 'var(--text-primary)' }}>
        <strong>{t('replay.banner')}</strong> {t('replay.scope')}
      </div>}
      {fullBleed ? (
        <main className="relative flex-1 overflow-hidden">{children}</main>
      ) : (
        <main className="flex-1 overflow-auto">{children}</main>
      )}
    </div>
  )
}
