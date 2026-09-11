import type { AlertLevel, UtciStressCategory } from '@/types/api'

// The alert level is COMPUTED BY THE BACKEND against absolute,
// locally-calibrated thresholds, and arrives on every ward and every
// forecast day as `alert_level`. This file no longer derives it.
//
// What used to be here - deriving a tier from a 0-1 `heat_risk` score -
// was the bug where the worst ward was always exactly 1.0 by
// construction, so it always read "Extreme" even on a mild day.

export const TIER_COLOR: Record<AlertLevel, string> = {
  none: '#1e8e3e',
  watch: '#f4b400',
  warning: '#fb8c00',
  danger: '#d50000',
  extreme: '#7f0000',
}

export const TIER_SOFT_COLOR: Record<AlertLevel, string> = {
  none: '#e3f3e6',
  watch: '#fdf0d0',
  warning: '#fce1c9',
  danger: '#f9d2d2',
  extreme: '#f0cccc',
}

export const TIER_ORDER: AlertLevel[] = [
  'none', 'watch', 'warning', 'danger', 'extreme',
]

export const TIER_RANK: Record<AlertLevel, number> = {
  none: 0, watch: 1, warning: 2, danger: 3, extreme: 4,
}

export function worstLevel(levels: AlertLevel[]): AlertLevel {
  return levels.reduce<AlertLevel>(
    (worst, level) => (TIER_RANK[level] > TIER_RANK[worst] ? level : worst),
    'none',
  )
}

// Thermal stress category -> tier, for labelling the UTCI reading
// itself. Still useful as a description of the thermal environment, but
// it is NOT what drives the map any more - a category says how hot it
// is, while the alert level says whether that is unusual here and now.
const CATEGORY_TO_TIER: Record<UtciStressCategory, AlertLevel> = {
  'extreme heat stress': 'extreme',
  'very strong heat stress': 'danger',
  'strong heat stress': 'warning',
  'moderate heat stress': 'watch',
  'no thermal stress': 'none',
  'slight cold stress': 'none',
  'moderate cold stress': 'none',
  'strong cold stress': 'none',
  'very strong cold stress': 'none',
  'extreme cold stress': 'none',
}

export function tierFromUtciCategory(category: UtciStressCategory): AlertLevel {
  return CATEGORY_TO_TIER[category] ?? 'none'
}

// ------------------------------------------------------------------
// Weather mode: a plain TEMPERATURE scale - one smooth, muted gradient
// so adjacent bands read as a continuous "how hot is it" progression
// rather than five clashing swatches. Deliberately less vivid than
// TIER_COLOR, which is a RISK scale: weather is ambient, risk is the
// signal that should pop. No hex value is shared between the two.
// ------------------------------------------------------------------
export type WeatherBand = 'cool' | 'mild' | 'warm' | 'hot' | 'extreme'

export const WEATHER_COLOR: Record<WeatherBand, string> = {
  cool: '#7a9cc6',
  mild: '#6fada4',
  warm: '#d3ab5c',
  hot: '#d4894f',
  extreme: '#c26b57',
}

export const WEATHER_ORDER: WeatherBand[] = [
  'cool', 'mild', 'warm', 'hot', 'extreme',
]

// Takes AIR TEMPERATURE in Celsius - not UTCI.
//
// These thresholds are air-temperature thresholds. They were briefly fed
// UTCI instead, which happened to look plausible only because UTCI was
// being computed from a mis-timezoned evening window and came out far
// too low. With that fixed, a normal May afternoon has a UTCI above 45,
// so feeding UTCI here would paint the entire city "extreme" all summer.
export function bandFromTemperature(airTempC: number): WeatherBand {
  if (airTempC >= 44) return 'extreme'
  if (airTempC >= 38) return 'hot'
  if (airTempC >= 32) return 'warm'
  if (airTempC >= 22) return 'mild'
  return 'cool'
}
