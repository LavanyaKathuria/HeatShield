import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useMapStore } from '@/store/useMapStore'
import { TIER_COLOR, TIER_RANK, worstLevel } from '@/lib/riskTiers'
import type { WardDailyRecord } from '@/types/api'

interface ForecastStripProps {
  dates: string[]
  timelineByDate: Map<string, WardDailyRecord[]>
  selectedWardId: string | null
}

// A compact, always-on floating forecast window (bottom-left, Google
// Weather-flavored) - separate from the ward panel so clicking a ward
// never buries the 5-day outlook. Clicking a day scrubs the whole
// map's active day via the shared store.
export function ForecastStrip({ dates, timelineByDate, selectedWardId }: ForecastStripProps) {
  const { t, i18n } = useTranslation()
  const dayIndex = useMapStore((s) => s.dayIndex)
  const setDayIndex = useMapStore((s) => s.setDayIndex)

  const days = useMemo(() => {
    return dates.map((date) => {
      const records = timelineByDate.get(date) ?? []
      const record = selectedWardId ? records.find((r) => r.ward_id === selectedWardId) : null
      const temp = record ? record.tmax : records.length > 0 ? Math.max(...records.map((r) => r.tmax)) : null
      // With no ward selected the dot shows the worst level anywhere in
      // the city that day - the same thing the map is showing.
      const tier = record
        ? record.alert_level
        : records.length > 0
          ? worstLevel(records.map((r) => r.alert_level))
          : null
      return { date, temp, tier }
    })
  }, [dates, timelineByDate, selectedWardId])

  if (days.length === 0) return null

  const temps = days.map((d) => d.temp).filter((v): v is number => v !== null)
  const min = temps.length ? Math.min(...temps) : 0
  const max = temps.length ? Math.max(...temps) : 1
  const range = Math.max(max - min, 1)

  function dayLabel(date: string, index: number) {
    if (index === 0) return t('forecast.today')
    if (index === 1) return t('forecast.tomorrow')
    return new Date(date).toLocaleDateString(i18n.language, { weekday: 'short' })
  }

  const sparklinePoints = days
    .map((d, i) => {
      const x = (i / Math.max(days.length - 1, 1)) * 100
      const y = d.temp === null ? 50 : 36 - ((d.temp - min) / range) * 32
      return `${x},${y}`
    })
    .join(' ')

  return (
    <div
      className={`place-panel absolute bottom-4 left-4 z-10 w-[240px] overflow-hidden rounded-lg ${selectedWardId ? 'hidden md:block' : ''}`}
    >
      <div className="px-3.5 pb-1 pt-3">
        <div className="text-[11px] font-medium uppercase tracking-wide" style={{ color: 'var(--text-tertiary)' }}>{t('forecast.title')}</div>
      </div>

      <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="h-8 w-full px-3.5" style={{ color: 'var(--accent)' }}>
        <polyline points={sparklinePoints} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>

      <div className="flex gap-1 px-2 pb-2.5 pt-1">
        {days.map((d, i) => (
          <button
            key={d.date}
            onClick={() => setDayIndex(i)}
            className="flex flex-1 flex-col items-center gap-1 rounded-md px-1.5 py-1.5 transition-colors"
            style={i === dayIndex ? { background: 'var(--accent-soft)' } : undefined}
          >
            <span className="text-[10px]" style={{ color: i === dayIndex ? 'var(--accent)' : 'var(--text-tertiary)' }}>{dayLabel(d.date, i)}</span>
            {d.temp !== null && (
              <span className="font-tabular text-[13px] font-semibold" style={{ color: 'var(--text-primary)' }}>{d.temp.toFixed(0)}°</span>
            )}
            {d.tier && TIER_RANK[d.tier] > 0 && (
              <span className="risk-dot" style={{ backgroundColor: TIER_COLOR[d.tier] }} />
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
