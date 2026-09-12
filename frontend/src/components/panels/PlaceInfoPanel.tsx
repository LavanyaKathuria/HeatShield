import { useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useMapStore } from '@/store/useMapStore'
import { TIER_COLOR, TIER_RANK, TIER_SOFT_COLOR } from '@/lib/riskTiers'
import { calculateHeatStress } from '@/lib/heatStress'
import { ConfidenceRange } from '@/components/common/ConfidenceRange'
import { MethodologyDrawer } from '@/components/panels/MethodologyDrawer'
import { SkeletonBlock } from '@/components/common/LoadingState'
import type {
  WardHeatRisk,
  WardDailyRecord,
  CitywideSummary,
} from '@/types/api'

interface PlaceInfoPanelProps {
  wards: WardHeatRisk[]
  wardTimeline: WardDailyRecord | null
  cityWardDays?: WardDailyRecord[]
  citywide: CitywideSummary | undefined
  loading?: boolean
}

function IconThermometer() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M9.5 9.1V3a1.5 1.5 0 0 0-3 0v6.1a2.5 2.5 0 1 0 3 0Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  )
}
function IconDroplet() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M8 2s4 4.5 4 7.5a4 4 0 1 1-8 0C4 6.5 8 2 8 2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  )
}
function IconWind() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <path d="M2 6h7a2 2 0 1 0-1.8-2.9M2 10h9.5a2 2 0 1 1-1.7 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}
function IconSun() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.6" stroke="currentColor" strokeWidth="1.3" />
      <path d="M8 1.5v1.4M8 13.1v1.4M14.5 8h-1.4M2.9 8H1.5M12.5 3.5l-1 1M4.5 11.5l-1 1M12.5 12.5l-1-1M4.5 4.5l-1-1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

// ------------------------------------------------------------------
// Shared typography primitives - ONE consistent scale used everywhere
// in the panel, so a number always looks like a number and a heading
// always looks like a heading. Every stat carries its own unit inline
// - never a number with the unit left to a separate caption elsewhere.
// ------------------------------------------------------------------

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <div
      className="mt-4 border-t pt-3 text-[12px] font-bold uppercase tracking-wide first:mt-0 first:border-t-0 first:pt-0"
      style={{ color: 'var(--text-primary)', borderColor: 'var(--border-subtle)' }}
    >
      {children}
    </div>
  )
}

function StatRow({ icon, label, value, tierColor }: { icon?: ReactNode; label: string; value: string; tierColor?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="flex items-center gap-1.5 text-[13px]" style={{ color: 'var(--text-secondary)' }}>
        {tierColor && <span className="risk-dot" style={{ backgroundColor: tierColor }} />}
        {icon}
        {label}
      </span>
      <span className="font-tabular whitespace-nowrap text-[14px] font-semibold" style={{ color: 'var(--text-primary)' }}>{value}</span>
    </div>
  )
}

function ValueTile({ icon, label, value }: { icon?: ReactNode; label: string; value: string }) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[12px]" style={{ color: 'var(--text-secondary)' }}>
        {icon}
        {label}
      </div>
      <div className="font-tabular text-[15px] font-semibold" style={{ color: 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

function CloseButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation()
  return (
    <button onClick={onClick} className="rounded p-1 transition-colors hover:bg-[var(--surface-sunken)]" aria-label={t('common.close')}>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 3l10 10M13 3L3 13" stroke="var(--text-tertiary)" strokeWidth="1.6" strokeLinecap="round" /></svg>
    </button>
  )
}

export function PlaceInfoPanel({
  wards,
  wardTimeline,
  cityWardDays = [],
  citywide,
  loading,
}: PlaceInfoPanelProps) {
  const mapMode = useMapStore((s) => s.mapMode)
  const selectedWardId = useMapStore((s) => s.selectedWardId)
  const selectWard = useMapStore((s) => s.selectWard)
  const [methodologyOpen, setMethodologyOpen] = useState(false)
  const [humidityOverride, setHumidityOverride] = useState<number | null>(null)

  const selectedWard = wards.find((w) => w.ward_id === selectedWardId) ?? null

  const worst = useMemo(() => {
    if (wards.length === 0) return null
    return wards.reduce((a, b) => (b.peak_utci_c > a.peak_utci_c ? b : a))
  }, [wards])

  const humidity = humidityOverride ?? wardTimeline?.afternoon_humidity_pct ?? null
  const whatIf = useMemo(() => {
    if (!wardTimeline || humidity === null) return null
    return calculateHeatStress(wardTimeline.tmax, humidity, wardTimeline.afternoon_wind_ms, wardTimeline.afternoon_solar_wm2)
  }, [wardTimeline, humidity])

  return (
    <>
      <div className="place-panel flex max-h-[80vh] w-full flex-col overflow-hidden rounded-t-2xl md:max-h-[calc(100vh-88px)] md:w-[340px] md:rounded-lg">
        <div className="sheet-handle md:hidden" />

        <div className="panel-content flex-1 overflow-y-auto px-4 pb-4 pt-1 md:pt-4" key={`${selectedWardId ?? 'citywide'}-${mapMode}`}>
          {loading || !citywide ? (
            <PanelSkeleton />
          ) : selectedWard ? (
            mapMode === 'weather' ? (
              <WeatherWardCard ward={selectedWard} wardDay={wardTimeline} onClose={() => selectWard(null)} />
            ) : (
              <HeatRiskWardCard
                ward={selectedWard}
                wardDay={wardTimeline}
                citywide={citywide}
                humidity={humidity}
                whatIfUtci={whatIf?.utciC ?? null}
                onHumidityChange={setHumidityOverride}
                onClose={() => selectWard(null)}
                onOpenMethodology={() => setMethodologyOpen(true)}
              />
            )
          ) : mapMode === 'weather' ? (
            <WeatherCityOverview worst={worst} />
          ) : (
            <HeatRiskCityOverview
              worst={worst}
              wardDays={cityWardDays}
              citywide={citywide}
              onOpenMethodology={() => setMethodologyOpen(true)}
            />
          )}
        </div>
      </div>

      {methodologyOpen && <MethodologyDrawer onClose={() => setMethodologyOpen(false)} />}
    </>
  )
}

function PanelSkeleton() {
  return (
    <div className="space-y-3">
      <SkeletonBlock className="h-4 w-24" />
      <SkeletonBlock className="h-6 w-48" />
      <div className="grid grid-cols-2 gap-3">
        <SkeletonBlock className="h-12" />
        <SkeletonBlock className="h-12" />
      </div>
      <SkeletonBlock className="h-20" />
    </div>
  )
}

// ------------------------------------------------------------------
// WEATHER mode - meteorological facts only. No risk tier, no
// mortality, no vulnerability breakdown - those belong to Heat Risk.
// ------------------------------------------------------------------

function WeatherWardCard({ ward, wardDay, onClose }: { ward: WardHeatRisk; wardDay: WardDailyRecord | null; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-[17px] font-semibold" style={{ color: 'var(--text-primary)' }}>{ward.ward_name}</h2>
        <CloseButton onClick={onClose} />
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-tabular text-[36px] font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>
          {wardDay ? `${wardDay.tmax.toFixed(0)}°` : `${ward.peak_utci_c.toFixed(0)}°`}
        </span>
        <span className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
          {t('thermometer.feelsLike')} {ward.peak_utci_c.toFixed(0)}°
        </span>
      </div>

      {wardDay && (
        <>
          <SectionHeading>{t('mapModes.weather')}</SectionHeading>
          <div className="grid grid-cols-2 gap-x-3 gap-y-3 pt-1">
            <ValueTile icon={<IconDroplet />} label={t('weather.humidity')} value={`${wardDay.afternoon_humidity_pct.toFixed(0)}%`} />
            <ValueTile icon={<IconWind />} label={t('weather.wind')} value={`${wardDay.afternoon_wind_ms.toFixed(0)} m/s`} />
            <ValueTile icon={<IconSun />} label={t('weather.radiation')} value={`${wardDay.afternoon_solar_wm2.toFixed(0)} W/m²`} />
          </div>
        </>
      )}
    </>
  )
}

function WeatherCityOverview({ worst }: { worst: WardHeatRisk | null }) {
  const { t } = useTranslation()
  if (!worst) return null
  return (
    <>
      <div className="text-[12px] font-bold uppercase tracking-wide" style={{ color: 'var(--text-primary)' }}>{t('mapModes.weather')}</div>
      <div className="mt-1.5 flex items-baseline gap-2">
        <span className="font-tabular text-[32px] font-semibold leading-none" style={{ color: 'var(--text-primary)' }}>{worst.peak_utci_c.toFixed(0)}°</span>
        <span className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>{worst.ward_name}</span>
      </div>
      <p className="mt-3 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>{t('place.selectPrompt')}</p>
    </>
  )
}

// ------------------------------------------------------------------
// HEAT RISK mode - health/risk signal. Temperature appears only as a
// small contextual value; the primary numbers are the risk tier and
// the modeled mortality figures.
// ------------------------------------------------------------------

function HeatRiskWardCard({
  ward,
  wardDay,
  citywide,
  humidity,
  whatIfUtci,
  onHumidityChange,
  onClose,
  onOpenMethodology,
}: {
  ward: WardHeatRisk
  wardDay: WardDailyRecord | null
  citywide: CitywideSummary
  humidity: number | null
  whatIfUtci: number | null
  onHumidityChange: (pct: number) => void
  onClose: () => void
  onOpenMethodology: () => void
}) {
  const { t } = useTranslation()
  const tier = ward.alert_level

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-[17px] font-semibold" style={{ color: 'var(--text-primary)' }}>{ward.ward_name}</h2>
        <CloseButton onClick={onClose} />
      </div>

      <div className="mt-1.5 flex items-center justify-between">
        <span className="badge" style={{ color: TIER_COLOR[tier], background: TIER_SOFT_COLOR[tier], fontSize: '13px', padding: '4px 12px' }}>
          {t('place.heatRisk')}: {t(`tiers.${tier}`)}
        </span>
        <span className="flex items-center gap-1 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
          <IconThermometer /> {ward.peak_utci_c.toFixed(0)}°
        </span>
      </div>

      <SectionHeading>{t('place.thermalIndex')}</SectionHeading>
      <div className="pt-1">
        <StatRow label={t('place.thermalIndex')} value={`${ward.peak_utci_c.toFixed(1)}°C (UTCI)`} />
        <p className="mb-1 -mt-1 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>{t(`utciCategories.${ward.peak_utci_stress_category}`)}</p>
        {/* The anomaly is what actually drives risk - an absolute
            reading says nothing without the local norm beside it. */}
        <StatRow label={t('place.normalForDate')} value={`${ward.utci_normal_c.toFixed(1)}°C`} />
        <StatRow
          label={t('place.aboveNormal')}
          value={`${ward.utci_anomaly_c >= 0 ? '+' : ''}${ward.utci_anomaly_c.toFixed(1)}°C`}
          tierColor={ward.utci_anomaly_c > 0 ? TIER_COLOR[tier] : undefined}
        />
        {wardDay && <StatRow icon={<IconDroplet />} label={t('weather.humidity')} value={`${wardDay.afternoon_humidity_pct.toFixed(0)}%`} />}
        {wardDay && <StatRow icon={<IconWind />} label={t('weather.wind')} value={`${wardDay.afternoon_wind_ms.toFixed(0)} m/s`} />}
        {/* WBGT is the occupational heat-exposure standard, and on days
            without a heat event it is what decides the ward's level.
            Leaving it out made two near-identical wards look
            inexplicably different. */}
        <StatRow label={t('place.workplaceHeat')} value={`${ward.wbgt_shade_c.toFixed(1)}°C (WBGT)`} />
      </div>

      <WhoIsAtRisk ward={ward} citywide={citywide} onOpenMethodology={onOpenMethodology} />

      {ward.recommended_action_key && (
        <>
          <SectionHeading>{t('place.recommendedResponse')}</SectionHeading>
          <p className="pt-1 text-[13px] leading-relaxed" style={{ color: 'var(--text-primary)' }}>
            {t(`recommendedActions.${ward.recommended_action_key}`)}
          </p>
        </>
      )}

      {wardDay && whatIfUtci !== null && (
        <details className="surface-sunken mt-4 p-2.5">
          <summary className="cursor-pointer text-[12px] font-medium" style={{ color: 'var(--text-secondary)' }}>
            {t('thermometer.title')}
          </summary>
          <div className="mt-2 flex items-center justify-between text-[12px]" style={{ color: 'var(--text-secondary)' }}>
            <span>{t('thermometer.humiditySlider')}</span>
            <span className="font-tabular font-medium" style={{ color: 'var(--text-primary)' }}>{humidity?.toFixed(0)}%</span>
          </div>
          <input
            type="range"
            min={5}
            max={100}
            step={1}
            value={humidity ?? 50}
            onChange={(e) => onHumidityChange(Number(e.target.value))}
            className="mt-1 w-full"
            style={{ accentColor: 'var(--accent)' }}
          />
          <p className="mt-2 text-[12px]" style={{ color: 'var(--text-primary)' }}>
            {t('thermometer.feelsLike')}: <span className="font-tabular font-semibold">{whatIfUtci.toFixed(0)}°C</span>
          </p>
        </details>
      )}
    </>
  )
}

function HeatRiskCityOverview({
  worst,
  wardDays,
  citywide,
  onOpenMethodology,
}: {
  worst: WardHeatRisk | null
  wardDays: WardDailyRecord[]
  citywide: CitywideSummary
  onOpenMethodology: () => void
}) {
  const { t, i18n } = useTranslation()
  const dayIndex = useMapStore((s) => s.dayIndex)
  const source = useMapStore((s) => s.source)
  const day = citywide.daily[dayIndex]
  const matchingDays = day ? wardDays.filter((record) => record.date === day.date) : []
  const maxValue = (key: 'tmax' | 'wbgt_shade_c') => {
    const values = matchingDays.map((record) => record[key]).filter(Number.isFinite)
    return values.length ? `${Math.max(...values).toFixed(1)}°C` : '—'
  }
  const cityTier = citywide.peak_alert_level
  const asOf = citywide.forecast_generated_at
    ? new Date(citywide.forecast_generated_at).toLocaleTimeString(i18n.language, { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <>
      <div className="text-[12px] font-bold uppercase tracking-wide" style={{ color: 'var(--text-primary)' }}>{t('heatStatus.headline')}</div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="badge" style={{ color: TIER_COLOR[cityTier], background: TIER_SOFT_COLOR[cityTier], fontSize: '12px' }}>
          {t(`tiers.${cityTier}`)}
        </span>
        <h2 className="text-[16px] font-semibold" style={{ color: 'var(--text-primary)' }}>{t('heatStatus.cityHeadline')}</h2>
      </div>
      <p className="mt-1.5 text-[13px]" style={{ color: 'var(--text-secondary)' }}>{t(`tierDescriptions.${cityTier}`)}</p>
      {asOf && <p className="mt-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{t('heatStatus.asOf', { time: asOf })}</p>}

      {day && <div className="surface-sunken mt-3 space-y-2 p-3">
        <p className="text-[12px] font-semibold">{t('heatNumbers.date', { date: day.date })}</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-3">
          <ValueTile icon={<IconThermometer />} label={t('heatNumbers.air')} value={maxValue('tmax')} />
          <ValueTile label={t('heatNumbers.utci')} value={Number.isFinite(day.utci_c) ? `${day.utci_c.toFixed(1)}°C` : '—'} />
          <ValueTile label={t('heatNumbers.wbgt')} value={maxValue('wbgt_shade_c')} />
          <ValueTile label={t('heatNumbers.ehf')} value={day.ehf !== null && Number.isFinite(day.ehf) ? day.ehf.toFixed(1) : '—'} />
        </div>
        <p className="text-[11px]" style={{ color: 'var(--text-tertiary)' }}>{t('heatNumbers.scope')}</p>
      </div>}

      {citywide.heatwave_detected && citywide.heatwave_duration_days > 0 && (
        <p className="surface-sunken mt-3 p-2.5 text-[12px]" style={{ color: 'var(--text-primary)' }}>
          {t(source === 'may_2024' ? 'heatNumbers.historicalDuration' : 'heatStatus.sustainedActive', { count: citywide.heatwave_duration_days })}
        </p>
      )}

      {worst && (
        <WhoIsAtRisk ward={worst} citywide={citywide} onOpenMethodology={onOpenMethodology} />
      )}

      <p className="mt-3 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>{t('place.selectPrompt')}</p>
    </>
  )
}

function InfoButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation()
  return (
    <button
      onClick={onClick}
      aria-label={t('mortality.aboutEstimate')}
      title={t('mortality.aboutEstimate')}
      className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-semibold transition-colors"
      style={{ color: 'var(--text-tertiary)', border: '1px solid var(--border-default)' }}
    >
      i
    </button>
  )
}

const GROUP_LABEL_KEY: Record<string, string> = {
  elderly: 'riskByGroup.elderly',
  children: 'riskByGroup.children',
  outdoor_workers: 'riskByGroup.outdoorWorkers',
  general: 'riskByGroup.general',
}

/**
 * Who this heat is dangerous for, and the citywide burden behind it.
 *
 * Groups are shown only when the backend has actually raised them to a
 * level - a list of every group at "none" tells the reader nothing and
 * trains them to skip the section. When nothing is raised, that fact is
 * stated plainly instead.
 *
 * Mortality stays CITYWIDE and is labelled as such. Ward-level death
 * counts do not exist in any data source; what the ward genuinely owns
 * is its thermal stress, its anomaly and its alert level.
 */
function WhoIsAtRisk({
  ward,
  citywide,
  onOpenMethodology,
}: {
  ward: WardHeatRisk
  citywide: CitywideSummary
  onOpenMethodology: () => void
}) {
  const { t } = useTranslation()

  const raised = (Object.entries(ward.group_levels) as [string, string][])
    .filter(([, level]) => level !== 'none')
    .sort((a, b) => TIER_RANK[b[1] as never] - TIER_RANK[a[1] as never])

  // Each group is triggered on a different measure, because mortality is
  // the wrong endpoint for most of them - a work/rest cycle is set by
  // WBGT, not by a death rate. Naming the measure and its value is what
  // makes a ward's level explicable; without it, two wards a tenth of a
  // degree apart look arbitrarily different.
  const TRIGGER: Record<string, { value: string; key: string }> = {
    outdoor_workers: {
      value: `${ward.wbgt_shade_c.toFixed(1)}°C`,
      key: 'place.trigger.wbgt',
    },
    children: {
      value: `${ward.peak_utci_c.toFixed(1)}°C`,
      key: 'place.trigger.utci',
    },
    elderly: {
      value: ward.elderly_per_100k.toFixed(2),
      key: 'place.trigger.elderlyRate',
    },
    general: {
      value: ward.ehf === null ? '—' : ward.ehf.toFixed(0),
      key: 'place.trigger.ehf',
    },
  }

  return (
    <>
      <SectionHeading>{t('place.atRisk')}</SectionHeading>
      <div className="pt-1">
        {raised.length === 0 ? (
          <p className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
            {t('place.noGroupAtRisk')}
          </p>
        ) : (
          raised.map(([group, level]) => (
            <div key={group}>
              <StatRow
                tierColor={TIER_COLOR[level as never]}
                label={t(GROUP_LABEL_KEY[group] ?? group)}
                value={t(`tiers.${level}`)}
              />
              {TRIGGER[group] && (
                <p className="mb-1 -mt-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
                  {t(TRIGGER[group].key, { value: TRIGGER[group].value })}
                </p>
              )}
            </div>
          ))
        )}
      </div>

      <SectionHeading>{t('mortality.citywideLabel')}</SectionHeading>
      <div className="pt-1">
        <div className="flex items-center justify-between">
          <span className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>
            {t('mortality.overForecast')}
          </span>
          <InfoButton onClick={onOpenMethodology} />
        </div>
        <ConfidenceRange
          point={citywide.estimated_total_excess_deaths}
          low={citywide.estimated_total_excess_deaths_low}
          high={citywide.estimated_total_excess_deaths_high}
        />
        <p className="mt-1 text-[11px]" style={{ color: 'var(--text-tertiary)' }}>
          {t('mortality.citywideScopeNote')}
        </p>
      </div>

      <button onClick={onOpenMethodology} className="mt-3 flex items-center gap-1.5 text-[12px] font-medium" style={{ color: 'var(--accent)' }}>
        <span className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-semibold" style={{ border: '1px solid var(--accent)' }}>i</span>
        {t('mortality.aboutEstimate')}
      </button>
    </>
  )
}
