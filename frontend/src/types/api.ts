// Types mirroring src/api.py's real response shapes. Keep in sync with
// the backend by hand - there is no shared schema generator yet.

export type UtciStressCategory =
  | 'extreme cold stress'
  | 'very strong cold stress'
  | 'strong cold stress'
  | 'moderate cold stress'
  | 'slight cold stress'
  | 'no thermal stress'
  | 'moderate heat stress'
  | 'strong heat stress'
  | 'very strong heat stress'
  | 'extreme heat stress'

// A stable key, not rendered text - the backend deliberately doesn't
// own English prose here (see src/api.py's recommended_action()); the
// frontend's i18n locale files ("recommendedActions.*") own the actual
// wording in all three languages.
export type RecommendedActionKey =
  | 'deploy_mobile_unit'
  | 'increase_ambulance_cooling'
  | 'increase_monitoring'
  | 'routine_monitoring'

// The alert level is now computed by the backend against absolute,
// locally-calibrated thresholds - it is no longer a frontend
// visualization concept derived from a relative 0-1 score.
export type AlertLevel = 'none' | 'watch' | 'warning' | 'danger' | 'extreme'

// How unusual the heat is for this place and date, from the Excess Heat
// Factor. "none" means the heat is within the seasonal norm, however hot
// it is in absolute terms.
export type EventSeverity = 'none' | 'low_intensity' | 'severe' | 'extreme'

export type RiskGroup = 'elderly' | 'children' | 'outdoor_workers' | 'general'

export type GroupLevels = Record<RiskGroup, AlertLevel>

export interface WardHeatRisk {
  ward_id: string
  ward_name: string
  peak_date: string

  peak_utci_c: number
  peak_utci_stress_category: UtciStressCategory

  // What is normal for that calendar date, and how far above it this is.
  // The anomaly - not the raw temperature - is what drives risk.
  utci_normal_c: number
  utci_anomaly_c: number

  wbgt_shade_c: number
  heat_index_c: number | null

  ehf: number | null
  event_severity: EventSeverity

  // City-scale burden evaluated at this ward's conditions. It ranks
  // wards against each other; it is NOT this ward's death count and must
  // never be summed across wards or shown as a ward figure.
  citywide_equivalent_excess_deaths: number

  elderly_per_100k: number
  highest_risk_group: RiskGroup | null

  alert_level: AlertLevel
  group_levels: GroupLevels

  is_beyond_observed_range: boolean
  recommended_action_key?: RecommendedActionKey
}

export interface CitywideDaily {
  date: string
  utci_c: number
  ehf: number | null
  event_severity: EventSeverity
  excess_deaths: number
  excess_deaths_low: number
  excess_deaths_high: number
  highest_risk_group: RiskGroup | null
}

// Mortality is reported CITYWIDE only. Ward-level death counts do not
// exist in any data source and are never produced by the backend.
export interface CitywideSummary {
  heatwave_detected: boolean
  heatwave_duration_days: number
  event_severity: EventSeverity
  peak_alert_level: AlertLevel
  estimated_total_excess_deaths: number
  estimated_total_excess_deaths_low: number
  estimated_total_excess_deaths_high: number
  daily: CitywideDaily[]
  scope: 'citywide'
  forecast_generated_at: string | null
}

export interface WardPriorityResponse {
  forecast_days: number
  citywide: CitywideSummary
  wards: WardHeatRisk[]
}

// Per-ward, per-day record from /ward-forecast-timeline - drives the
// 5-day time slider with real day-by-day data, not a client-side guess.
export interface WardDailyRecord {
  ward_id: string
  ward_name: string
  date: string

  utci_c: number
  utci_stress_category: UtciStressCategory
  utci_normal_c: number
  utci_anomaly_c: number
  night_anomaly_c: number | null

  tmax: number
  tmin: number
  afternoon_humidity_pct: number
  afternoon_wind_ms: number
  afternoon_solar_wm2: number
  wbgt_shade_c: number
  heat_index_c: number | null

  ehf: number | null
  event_severity: EventSeverity

  elderly_per_100k: number
  highest_risk_group: RiskGroup | null

  alert_level: AlertLevel
  group_levels: GroupLevels

  recommended_action_key: RecommendedActionKey
}

export interface WardForecastTimelineResponse {
  forecast_days: number
  dates: string[]
  days: WardDailyRecord[]
}

export interface HeatEventDay {
  date: string
  utci_c: number
  ehf: number | null
  severity: EventSeverity
}

export interface HeatEventResponse {
  forecast_days: number
  heatwave_detected: boolean
  event_severity: EventSeverity
  days: HeatEventDay[]
  citywide: CitywideSummary
  wards_affected: string[]
}

// Kept as an alias so existing tier-colour code keeps compiling; the
// backend now owns the level, so this is the same union.
export type AlertTier = AlertLevel

