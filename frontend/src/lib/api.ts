import type {
  HeatEventResponse,
  WardForecastTimelineResponse,
  WardPriorityResponse,
} from '@/types/api'

// Proxied through Vite's dev server (see vite.config.ts) to avoid CORS
// friction in dev; in production this should point at the deployed
// FastAPI host directly.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

type Params = Record<string, string | number | undefined>

function queryString(params?: Params): string {
  if (!params) return ''

  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined)
    .map(([key, value]) => [key, String(value)])

  return entries.length ? '?' + new URLSearchParams(entries).toString() : ''
}

async function get<T>(path: string, params?: Params): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}${queryString(params)}`)

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed`, response.status)
  }

  return response.json() as Promise<T>
}

export const api = {
  wardPriority: (forecastDays = 5, source = 'live') =>
    get<WardPriorityResponse>('/ward-priority', { forecast_days: forecastDays, source }),

  wardForecastTimeline: (forecastDays = 5, source = 'live') =>
    get<WardForecastTimelineResponse>('/ward-forecast-timeline', {
      forecast_days: forecastDays,
      source,
    }),

  heatEvent: (forecastDays = 5, source = 'live') =>
    get<HeatEventResponse>('/heat-event', { forecast_days: forecastDays, source }),
}
