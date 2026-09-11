import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

const FORECAST_DAYS = 5

export function useWardPriority() {
  return useQuery({
    queryKey: ['ward-priority', FORECAST_DAYS],
    queryFn: () => api.wardPriority(FORECAST_DAYS),
    refetchInterval: 5 * 60_000,
  })
}

export function useWardForecastTimeline() {
  return useQuery({
    queryKey: ['ward-forecast-timeline', FORECAST_DAYS],
    queryFn: () => api.wardForecastTimeline(FORECAST_DAYS),
    refetchInterval: 5 * 60_000,
  })
}

export function useHeatEvent() {
  return useQuery({
    queryKey: ['heat-event', FORECAST_DAYS],
    queryFn: () => api.heatEvent(FORECAST_DAYS),
    refetchInterval: 5 * 60_000,
  })
}


