import { useMemo, useState } from 'react'
import { WhatsAppAlerts } from '@/components/panels/WhatsAppAlerts'
import { useTranslation } from 'react-i18next'
import { DashboardShell } from '@/components/layout/DashboardShell'
import { WardChoroplethMap } from '@/components/map/WardChoroplethMap'
import { MapModeControl } from '@/components/map/MapModeControl'
import { ForecastStrip } from '@/components/map/ForecastStrip'
import { PlaceInfoPanel } from '@/components/panels/PlaceInfoPanel'
import { useWardPriority, useWardForecastTimeline } from '@/hooks/useForecastData'
import { useMapStore } from '@/store/useMapStore'
import { useAuthStore } from '@/store/useAuthStore'
import type { WardDailyRecord, WardHeatRisk } from '@/types/api'

// Scoping (demo-level - see ProfileMenu.tsx): Nodal Officer sees every
// ward; Ward Officer/Hospital/Employer see only the ward tied to their
// account. Same real data, different scoped view.
function scopeWards(wards: WardHeatRisk[], role: string, ownWardId: string | null): WardHeatRisk[] {
  if (role === 'nodal_officer' || !ownWardId) return wards
  return wards.filter((w) => w.ward_id === ownWardId)
}

export function CorporateDashboard() {
  const [alertsOpen, setAlertsOpen] = useState(false)
  const { t } = useTranslation()
  const priorityQuery = useWardPriority()
  const timelineQuery = useWardForecastTimeline()
  const dayIndex = useMapStore((s) => s.dayIndex)
  const selectedWardId = useMapStore((s) => s.selectedWardId)
  const activeRole = useAuthStore((s) => s.activeRole)
  const corporateAccount = useAuthStore((s) => s.corporateAccount)

  const scopedWards = useMemo(
    () => (priorityQuery.data ? scopeWards(priorityQuery.data.wards, activeRole, corporateAccount?.ward_id ?? null) : []),
    [priorityQuery.data, activeRole, corporateAccount]
  )

  // All ward-day records grouped by date (for the citywide day-picker
  // strip) and by ward for the active day (for the map + selected
  // ward's readout) - both derived from one real fetch, no separate
  // per-ward requests.
  const timelineByDate = useMemo(() => {
    const map = new Map<string, WardDailyRecord[]>()
    if (!timelineQuery.data) return map
    for (const record of timelineQuery.data.days) {
      const list = map.get(record.date) ?? []
      list.push(record)
      map.set(record.date, list)
    }
    return map
  }, [timelineQuery.data])

  const wardsByDay = useMemo(() => {
    if (!timelineQuery.data) return null
    const activeDate = timelineQuery.data.dates[dayIndex]
    const map = new Map<string, WardDailyRecord>()
    for (const record of timelineByDate.get(activeDate) ?? []) map.set(record.ward_id, record)
    return map
  }, [timelineQuery.data, timelineByDate, dayIndex])

  const wardTimeline = selectedWardId ? (wardsByDay?.get(selectedWardId) ?? null) : null

  return (
    <DashboardShell fullBleed navCenter={<MapModeControl />}>
      <div className="absolute left-4 top-16 z-30">
        <button className="btn btn-secondary" onClick={() => setAlertsOpen(!alertsOpen)}>{t('whatsapp.title')}</button>
      </div>
      {alertsOpen && <div className="absolute inset-x-4 top-28 bottom-4 z-40 overflow-y-auto md:left-4 md:right-auto md:w-[460px]" style={{ background: 'var(--surface-card)' }}>
        <button className="btn btn-secondary m-3" onClick={() => setAlertsOpen(false)}>{t('common.close')}</button>
        <WhatsAppAlerts key={corporateAccount?.id} />
      </div>}
      <div className="absolute inset-0">
        <WardChoroplethMap wardSummaries={scopedWards} wardsByDay={wardsByDay} />
      </div>

      {priorityQuery.isError && (
        <div
          className="absolute left-1/2 top-4 flex -translate-x-1/2 items-center gap-3 rounded-md px-3.5 py-2 text-[13px]"
          style={{ background: 'var(--surface-card)', boxShadow: 'var(--shadow-md)', color: 'var(--risk-danger)' }}
        >
          {t('common.forecastUnavailable')}
          <button onClick={() => priorityQuery.refetch()} className="btn btn-secondary !px-2.5 !py-1 !text-[12px]">
            {t('common.retry')}
          </button>
        </div>
      )}

      {timelineQuery.data && (
        <ForecastStrip dates={timelineQuery.data.dates} timelineByDate={timelineByDate} selectedWardId={selectedWardId} />
      )}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-end md:inset-x-auto md:inset-y-0 md:right-4 md:items-center">
        <div className="pointer-events-auto w-full md:w-auto md:py-4">
          <PlaceInfoPanel
            wards={scopedWards}
            wardTimeline={wardTimeline}
            cityWardDays={wardsByDay ? Array.from(wardsByDay.values()) : []}
            citywide={priorityQuery.data?.citywide}
            loading={priorityQuery.isLoading}
          />
        </div>
      </div>
    </DashboardShell>
  )
}
