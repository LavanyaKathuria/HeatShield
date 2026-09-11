import type { FeatureCollection, Geometry } from 'geojson'

export interface WardProperties {
  sourcewardcode: string
  sourcewardname: string
  [key: string]: unknown
}

export type WardFeatureCollection = FeatureCollection<Geometry, WardProperties>

let cached: WardFeatureCollection | null = null

export async function loadWardGeojson(): Promise<WardFeatureCollection> {
  if (cached) return cached
  const response = await fetch('/wards_ahmedabad.geojson')
  if (!response.ok) throw new Error('Failed to load ward boundaries')
  cached = (await response.json()) as WardFeatureCollection
  return cached
}
