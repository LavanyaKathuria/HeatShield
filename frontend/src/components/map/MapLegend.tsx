import { useTranslation } from 'react-i18next'
import { TIER_COLOR, TIER_ORDER, WEATHER_COLOR, WEATHER_ORDER } from '@/lib/riskTiers'
import { useMapStore } from '@/store/useMapStore'

export function MapLegend() {
  const { t } = useTranslation()
  const mapMode = useMapStore((s) => s.mapMode)
  const selectedWardId = useMapStore((s) => s.selectedWardId)

  const items =
    mapMode === 'weather'
      ? WEATHER_ORDER.map((band) => ({ key: band, color: WEATHER_COLOR[band], label: t(`weatherBands.${band}`) }))
      : TIER_ORDER.map((tier) => ({ key: tier, color: TIER_COLOR[tier], label: t(`tiers.${tier}`) }))

  return (
    <div
      className={`absolute bottom-4 left-1/2 z-10 -translate-x-1/2 items-center gap-3 rounded-md px-3 py-2 text-[11px] ${selectedWardId ? 'hidden md:flex' : 'flex'}`}
      style={{ background: 'var(--surface-card)', border: '1px solid var(--border-subtle)', boxShadow: 'var(--shadow-sm)', color: 'var(--text-secondary)' }}
    >
      {items.map((item) => (
        <div key={item.key} className="flex items-center gap-1.5">
          <span className="risk-dot" style={{ backgroundColor: item.color }} />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  )
}
