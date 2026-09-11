import { create } from 'zustand'

// Two map modes: raw observed/forecast conditions (weather) vs. a
// single combined Heat Risk tier that folds together thermal stress
// (UTCI) and modeled mortality risk - see lib/riskTiers.ts's
// combinedHeatRiskTier() for how they're merged. The ward info panel
// itself always shows every real value regardless of which mode is
// active; the mode only changes what the map polygons are colored by.
export type MapMode = 'weather' | 'heat_risk'

interface MapState {
  mapMode: MapMode
  selectedWardId: string | null
  // Index into the /ward-forecast-timeline `dates` array - drives the
  // 5-day timeline scrubber.
  dayIndex: number

  setMapMode: (mode: MapMode) => void
  selectWard: (wardId: string | null) => void
  setDayIndex: (index: number) => void
}

export const useMapStore = create<MapState>((set) => ({
  mapMode: 'heat_risk',
  selectedWardId: null,
  dayIndex: 0,

  setMapMode: (mapMode) => set({ mapMode }),
  selectWard: (selectedWardId) => set({ selectedWardId }),
  setDayIndex: (dayIndex) => set({ dayIndex }),
}))
