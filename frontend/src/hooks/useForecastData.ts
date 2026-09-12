import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useMapStore } from '@/store/useMapStore'

const FORECAST_DAYS = 5

export function useWardPriority() {
  const source = useMapStore((s) => s.source)
  return useQuery({
    queryKey: ['ward-priority', FORECAST_DAYS, source],
    queryFn: () => api.wardPriority(FORECAST_DAYS, source),
    refetchInterval: 5 * 60_000,
  })
}

export function useWardForecastTimeline() {
  const source = useMapStore((s) => s.source)
  return useQuery({
    queryKey: ['ward-forecast-timeline', FORECAST_DAYS, source],
    queryFn: () => api.wardForecastTimeline(FORECAST_DAYS, source),
    refetchInterval: 5 * 60_000,
  })
}

export function useHeatEvent() {
  const source = useMapStore((s) => s.source)
  return useQuery({
    queryKey: ['heat-event', FORECAST_DAYS, source],
    queryFn: () => api.heatEvent(FORECAST_DAYS, source),
    refetchInterval: 5 * 60_000,
  })
}


