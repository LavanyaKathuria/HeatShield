import type * as maplibregl from 'maplibre-gl'

// Re-skins CARTO's OpenMapTiles-schema vector basemap with Google
// Maps' actual color relationships (land/water/parks/roads/labels),
// rather than shipping a generic gray/blue theme or depending on a
// paid Google Maps tile API key. The underlying vector data is
// unchanged - only paint properties are overridden, layer by layer,
// once the style has finished loading.
//
// Palette source: the exact values given for this product -
// background #F8F9FA, water #AECBFA, parks #C8E6C9, road neutrals
// #E8EAED / #DADCE0, text #202124 / #5F6368.

const LAND = '#F8F9FA'
const PARK = '#C8E6C9'
const BUILT_UP = '#EDEDEA'
const RESIDENTIAL = '#E8EAED'
const WATER = '#AECBFA'
const NEUTRAL_LIGHT = '#DADCE0'
const NEUTRAL_LIGHTER = '#E8EAED'
const ROAD_LOCAL_FILL = '#FFFFFF'
const ROAD_ARTERIAL_FILL = '#ECECEC'
const HIGHWAY_FILL = '#FBD9A5'
const HIGHWAY_CASE = '#EFC078'
const COUNTRY_OUTLINE = '#BDC1C6'
const TEXT_MAJOR = '#3C4043'
const TEXT_MINOR = '#5F6368'
const TEXT_ROAD = '#80868B'
const TEXT_FAINT = '#BDC1C6'

const MAJOR_PLACE_LAYERS = new Set([
  'place_country_1', 'place_country_2', 'place_state', 'place_continent',
  'place_city_r5', 'place_city_r6', 'place_capital_dot_z7',
])

function setFill(map: maplibregl.Map, id: string, color: string) {
  try {
    if (map.getLayer(id)) map.setPaintProperty(id, 'fill-color', color)
  } catch {
    /* layer shape didn't match - skip rather than crash the map */
  }
}
function setLine(map: maplibregl.Map, id: string, color: string) {
  try {
    if (map.getLayer(id)) map.setPaintProperty(id, 'line-color', color)
  } catch {
    /* ignore */
  }
}
function setText(map: maplibregl.Map, id: string, color: string) {
  try {
    if (map.getLayer(id)) map.setPaintProperty(id, 'text-color', color)
  } catch {
    /* ignore */
  }
}

export function applyGoogleMapsBasemapTheme(map: maplibregl.Map) {
  const style = map.getStyle()
  if (!style?.layers) return

  for (const layer of style.layers) {
    const id = layer.id

    if (layer.type === 'background') {
      try {
        map.setPaintProperty(id, 'background-color', LAND)
      } catch {
        /* ignore */
      }
      continue
    }

    if (layer.type === 'fill') {
      if (id === 'landcover' || id === 'landuse') setFill(map, id, LAND)
      else if (id === 'landuse_residential') setFill(map, id, RESIDENTIAL)
      else if (id.startsWith('park_')) setFill(map, id, PARK)
      else if (id === 'water' || id === 'water_shadow') setFill(map, id, WATER)
      else if (id.startsWith('building')) setFill(map, id, BUILT_UP)
      continue
    }

    if (layer.type === 'line') {
      if (id === 'waterway') { setLine(map, id, WATER); continue }
      if (id.startsWith('boundary_country_outline')) { setLine(map, id, COUNTRY_OUTLINE); continue }
      if (id.startsWith('boundary')) { setLine(map, id, NEUTRAL_LIGHT); continue }
      if (id.startsWith('aeroway')) { setLine(map, id, NEUTRAL_LIGHT); continue }
      if (id.includes('rail')) { setLine(map, id, NEUTRAL_LIGHT); continue }

      // Roads: distinguish the wide "case" (casing/outline) from the
      // narrower "fill" (the road surface color drawn on top of it),
      // and highways from arterial/local streets.
      const isHighway = id.includes('mot') || id.includes('trunk')
      const isCase = id.includes('case')

      if (isHighway) {
        setLine(map, id, isCase ? HIGHWAY_CASE : HIGHWAY_FILL)
      } else if (id.includes('minor') || id.includes('service') || id.includes('path')) {
        setLine(map, id, isCase ? NEUTRAL_LIGHT : ROAD_LOCAL_FILL)
      } else if (id.includes('sec') || id.includes('pri')) {
        setLine(map, id, isCase ? NEUTRAL_LIGHT : ROAD_ARTERIAL_FILL)
      } else {
        setLine(map, id, NEUTRAL_LIGHTER)
      }
      continue
    }

    if (layer.type === 'symbol') {
      if (id.startsWith('place_')) setText(map, id, MAJOR_PLACE_LAYERS.has(id) ? TEXT_MAJOR : TEXT_MINOR)
      else if (id.startsWith('roadname_')) setText(map, id, TEXT_ROAD)
      else if (id.startsWith('watername_') || id === 'waterway_label') setText(map, id, TEXT_MINOR)
      else if (id.startsWith('poi_')) setText(map, id, TEXT_MINOR)
      else if (id === 'housenumber') setText(map, id, TEXT_FAINT)
    }
  }
}
