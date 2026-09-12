import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import type { MapLayerMouseEvent } from 'maplibre-gl'
import { loadWardGeojson } from '@/lib/wardGeojson'
import { applyGoogleMapsBasemapTheme } from '@/lib/googleMapsTheme'
import { useMapStore } from '@/store/useMapStore'
import {
  TIER_COLOR,
  WEATHER_COLOR,
  bandFromTemperature,
} from '@/lib/riskTiers'
import type { WardHeatRisk, WardDailyRecord } from '@/types/api'
import { LoadingState } from '@/components/common/LoadingState'
import { ErrorState } from '@/components/common/ErrorState'
import { MapLegend } from '@/components/map/MapLegend'
import { useTranslation } from 'react-i18next'

const AHMEDABAD_CENTER: [number, number] = [72.5714, 23.0225]
const AHMEDABAD_ZOOM = 10.6
const NEUTRAL_FILL = '#c7cdd4'

// CARTO's free, no-API-key vector basemap. Light/"positron" rather
// than a dark style - a GIS reference map should read like a neutral
// backdrop for the risk data, not a mood board.
const BASE_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

const WARDS_SOURCE_ID = 'wards'
const WARDS_FILL_LAYER = 'wards-fill'
const WARDS_LINE_LAYER = 'wards-line'
const WARDS_SELECTED_LINE_LAYER = 'wards-selected-line'

interface WardChoroplethMapProps {
  wardsByDay: Map<string, WardDailyRecord> | null
  wardSummaries: WardHeatRisk[]
}

export function WardChoroplethMap({ wardsByDay, wardSummaries }: WardChoroplethMapProps) {
  const { t } = useTranslation()
  const mapMode = useMapStore((s) => s.mapMode)
  const selectedWardId = useMapStore((s) => s.selectedWardId)
  const selectWard = useMapStore((s) => s.selectWard)

  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const hoveredIdRef = useRef<string | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [geojson, setGeojson] = useState<Awaited<ReturnType<typeof loadWardGeojson>> | null>(null)
  const [attentionOnly, setAttentionOnly] = useState(false)

  useEffect(() => {
    loadWardGeojson()
      .then(setGeojson)
      .catch(() => setError(t('map.errorLoadingBoundaries')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Per-ward color, recomputed whenever the mode or the selected day
  // changes. Weather mode colors by real forecast air temperature; Heat
  // Risk colors by the backend's alert level, which is computed against
  // absolute, locally-calibrated thresholds.
  const colorByWard = useMemo(() => {
    const map = new Map<string, string>()

    const setFromDay = (wardId: string, day: WardDailyRecord) => {
      map.set(
        wardId,
        mapMode === 'weather'
          ? WEATHER_COLOR[bandFromTemperature(day.tmax)]
          : TIER_COLOR[day.alert_level],
      )
    }

    // Before the per-day timeline resolves, only the ward-priority
    // summary is available and it carries no dry-bulb temperature. Its
    // peak day's UTCI is a felt temperature on a different scale
    // entirely - roughly ten degrees above air temperature in summer -
    // so it cannot be fed to the air-temperature bands. Weather mode
    // holds its previous color for that one round trip rather than
    // painting the city a false "extreme".
    const setFromSummary = (w: WardHeatRisk) => {
      if (mapMode === 'heat_risk') {
        map.set(w.ward_id, TIER_COLOR[w.alert_level])
      }
    }

    if (wardsByDay) {
      for (const [wardId, day] of wardsByDay) setFromDay(wardId, day)
    } else {
      for (const w of wardSummaries) setFromSummary(w)
    }

    return map
  }, [wardsByDay, wardSummaries, mapMode])

  const attentionCount = useMemo(() => {
    if (mapMode === 'weather') return 0

    if (wardsByDay) {
      let count = 0
      for (const day of wardsByDay.values()) {
        if (day.alert_level !== 'none') count++
      }
      return count
    }

    return wardSummaries.filter((w) => w.alert_level !== 'none').length
  }, [wardsByDay, wardSummaries, mapMode])

  // Initialize the map once the ward boundaries are loaded, and add the
  // source/layers directly inside THIS instance's own 'load' handler
  // (not via a decoupled mapReady-state effect). React 19 StrictMode
  // double-invokes this effect in dev: mount -> cleanup -> mount again.
  // The first map's 'load' event can still be in flight when cleanup
  // tears it down; if layer setup lived in a separate effect keyed off
  // a shared `mapReady` boolean, that stale event could flip it true
  // before the second (real) map instance had finished loading its
  // style, so addSource/addLayer would throw against a style that
  // wasn't done loading yet - silently blanking the map. Capturing
  // `map` in the closure and checking it's still the current instance
  // before touching it avoids that race entirely.
  useEffect(() => {
    if (!containerRef.current || !geojson || mapRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE,
      center: AHMEDABAD_CENTER,
      zoom: AHMEDABAD_ZOOM,
      attributionControl: { compact: true },
      // A bare page-scroll over the map must never hijack the page -
      // this requires ctrl/cmd+scroll to zoom (and shows a small,
      // dismissable hint), exactly like an embedded Google Map.
      cooperativeGestures: true,
    })

    popupRef.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })

    map.on('load', () => {
      if (mapRef.current !== map) return // stale instance from a StrictMode double-invoke - ignore

      applyGoogleMapsBasemapTheme(map)

      map.addSource(WARDS_SOURCE_ID, { type: 'geojson', data: geojson, promoteId: 'sourcewardcode' })

      map.addLayer({
        id: WARDS_FILL_LAYER,
        type: 'fill',
        source: WARDS_SOURCE_ID,
        paint: {
          'fill-color': NEUTRAL_FILL,
          // Strong and saturated by design - the heat layer is the
          // primary signal; the basemap underneath supplies geographic
          // context (roads/water/labels), not the other way around.
          'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.85, 0.75],
        },
      })

      map.addLayer({
        id: WARDS_LINE_LAYER,
        type: 'line',
        source: WARDS_SOURCE_ID,
        paint: {
          'line-color': '#ffffff',
          'line-width': 1,
        },
      })

      map.addLayer({
        id: WARDS_SELECTED_LINE_LAYER,
        type: 'line',
        source: WARDS_SOURCE_ID,
        filter: ['==', ['get', 'sourcewardcode'], ''],
        paint: {
          'line-color': '#1a73e8',
          'line-width': 2.5,
        },
      })

      map.on('click', WARDS_FILL_LAYER, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0]
        const wardId = feature?.properties?.sourcewardcode as string | undefined
        if (!wardId) return

        selectWard(wardId)

        map.easeTo({ center: e.lngLat, zoom: Math.max(map.getZoom(), 12), duration: 500 })
      })

      // Clicking the basemap outside any ward - not just the panel's
      // close button - should deselect too, matching how a Google Maps
      // place card dismisses when you tap away from the pin. The actual
      // zoom-out happens in the selectedWardId effect below, so both
      // paths (click-away and the panel's X) share one camera move.
      map.on('click', (e: MapLayerMouseEvent) => {
        const hits = map.queryRenderedFeatures(e.point, { layers: [WARDS_FILL_LAYER] })
        if (hits.length === 0) selectWard(null)
      })

      map.on('mousemove', WARDS_FILL_LAYER, (e: MapLayerMouseEvent) => {
        map.getCanvas().style.cursor = 'pointer'
        const feature = e.features?.[0]
        const wardId = feature?.properties?.sourcewardcode as string | undefined
        const wardName = feature?.properties?.sourcewardname as string | undefined

        if (wardId !== hoveredIdRef.current) {
          if (hoveredIdRef.current) {
            map.setFeatureState({ source: WARDS_SOURCE_ID, id: hoveredIdRef.current }, { hover: false })
          }
          if (wardId) {
            map.setFeatureState({ source: WARDS_SOURCE_ID, id: wardId }, { hover: true })
          }
          hoveredIdRef.current = wardId ?? null
        }

        if (wardName && popupRef.current) {
          popupRef.current.setLngLat(e.lngLat).setHTML(`<strong>${wardName}</strong>`).addTo(map)
        }
      })

      map.on('mouseleave', WARDS_FILL_LAYER, () => {
        map.getCanvas().style.cursor = ''
        popupRef.current?.remove()
        if (hoveredIdRef.current) {
          map.setFeatureState({ source: WARDS_SOURCE_ID, id: hoveredIdRef.current }, { hover: false })
          hoveredIdRef.current = null
        }
      })

      setMapReady(true)
      setError(null)
    })

    map.on('error', (e) => {
      console.error('MapLibre error', e)
      // Transient tile errors must not remove an already working heat layer.
      if (mapRef.current === map && !map.getLayer(WARDS_FILL_LAYER)) setError(t('map.errorLoadingBasemap'))
    })

    mapRef.current = map

    return () => {
      map.remove()
      if (mapRef.current === map) mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geojson])

  // Repaint fill color + opacity whenever the color data or the
  // "needs attention" filter changes - `match`/`case` expressions
  // built from the real current colorByWard map, evaluated by
  // MapLibre on the GPU rather than per-feature React re-renders.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !map.getLayer(WARDS_FILL_LAYER)) return

    const colorExpression: (string | number | string[])[] = ['match', ['get', 'sourcewardcode']]
    const dimExpression: (string | number | string[])[] = ['match', ['get', 'sourcewardcode']]

    for (const [wardId, color] of colorByWard) {
      colorExpression.push(wardId, color)
      const dim = attentionOnly && mapMode !== 'weather' && color === TIER_COLOR.none
      dimExpression.push(wardId, dim ? 1 : 0)
    }
    colorExpression.push(NEUTRAL_FILL)
    dimExpression.push(0)

    // Heat Risk stays bright/saturated (0.75-0.85) since it's the
    // primary alert signal; Weather is deliberately more subdued
    // (0.5-0.6) as an ambient/informational layer, not an alarm.
    const [baseOpacity, hoverOpacity] = mapMode === 'weather' ? [0.5, 0.6] : [0.75, 0.85]

    // During source switching there are no cases; an empty match is invalid.
    map.setPaintProperty(WARDS_FILL_LAYER, 'fill-color', colorByWard.size ? colorExpression as unknown as maplibregl.ExpressionSpecification : NEUTRAL_FILL)
    map.setPaintProperty(WARDS_FILL_LAYER, 'fill-opacity', [
      'case',
      ['==', colorByWard.size ? dimExpression : 0, 1],
      0.08,
      ['boolean', ['feature-state', 'hover'], false],
      hoverOpacity,
      baseOpacity,
    ] as unknown as maplibregl.ExpressionSpecification)
  }, [colorByWard, mapReady, attentionOnly, mapMode])

  // Highlight the selected ward with an accent-colored outline.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !map.getLayer(WARDS_SELECTED_LINE_LAYER)) return

    map.setFilter(WARDS_SELECTED_LINE_LAYER, ['==', ['get', 'sourcewardcode'], selectedWardId ?? ''])
  }, [selectedWardId, mapReady])

  // Deselecting a ward - by clicking away or closing the info panel -
  // returns the camera to the citywide view, mirroring the zoom-in on
  // selection instead of leaving the map stuck at ward-level zoom.
  useEffect(() => {
    if (!mapReady || selectedWardId !== null) return
    mapRef.current?.easeTo({ center: AHMEDABAD_CENTER, zoom: AHMEDABAD_ZOOM, bearing: 0, pitch: 0, duration: 500 })
  }, [selectedWardId, mapReady])

  function zoomIn() {
    mapRef.current?.zoomIn({ duration: 250 })
  }
  function zoomOut() {
    mapRef.current?.zoomOut({ duration: 250 })
  }
  function recenter() {
    mapRef.current?.easeTo({ center: AHMEDABAD_CENTER, zoom: AHMEDABAD_ZOOM, bearing: 0, pitch: 0, duration: 500 })
  }
  function toggleFullscreen() {
    const el = containerRef.current?.parentElement
    if (!el) return
    if (document.fullscreenElement) document.exitFullscreen()
    else el.requestFullscreen()
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={containerRef} className="h-full w-full" />
      {error && <div className="absolute left-4 top-28 z-10"><ErrorState message={error} /></div>}

      {mapReady && mapMode !== 'weather' && (
        <div
          className="absolute left-4 top-4 flex items-center gap-1.5 rounded-md px-1 py-1 text-[12px] font-medium"
          style={{ background: 'var(--surface-card)', border: '1px solid var(--border-subtle)', boxShadow: 'var(--shadow-sm)' }}
        >
          <button
            onClick={() => setAttentionOnly(false)}
            className="rounded px-2.5 py-1 transition-colors"
            style={!attentionOnly ? { background: 'var(--surface-sunken)', color: 'var(--text-primary)' } : { color: 'var(--text-tertiary)' }}
          >
            {t('map.filterAll')}
          </button>
          <button
            onClick={() => setAttentionOnly(true)}
            className="flex items-center gap-1.5 rounded px-2.5 py-1 transition-colors"
            style={attentionOnly ? { background: 'var(--accent-soft)', color: 'var(--accent)' } : { color: 'var(--text-tertiary)' }}
          >
            {t('map.filterAttention')}
            <span
              className="rounded-full px-1.5 text-[10px] font-semibold"
              style={{ background: attentionOnly ? 'var(--accent)' : 'var(--surface-sunken)', color: attentionOnly ? '#fff' : 'var(--text-tertiary)' }}
            >
              {attentionCount}
            </span>
          </button>
        </div>
      )}

      {mapReady && (
        <div className="absolute bottom-6 right-3 flex flex-col gap-2">
          <div className="map-control-stack">
            <button onClick={zoomIn} className="map-control-btn" aria-label={t('map.zoomIn')}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
            </button>
            <button onClick={zoomOut} className="map-control-btn" aria-label={t('map.zoomOut')}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
            </button>
          </div>
          <button onClick={recenter} className="map-control-btn rounded-md" aria-label={t('map.recenter')}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
              <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
          <button onClick={toggleFullscreen} className="map-control-btn rounded-md" aria-label={t('map.fullscreen')}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 6V2h4M14 6V2h-4M2 10v4h4M14 10v4h-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      )}

      {mapReady && <MapLegend />}

      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: 'var(--surface-sunken)' }}>
          <LoadingState label={t('map.loadingBoundaries')} />
        </div>
      )}
    </div>
  )
}
