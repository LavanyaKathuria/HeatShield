import { useTranslation } from 'react-i18next'
import { useMapStore, type MapMode } from '@/store/useMapStore'

const MODES: MapMode[] = ['weather', 'heat_risk']

// Weather colors the map by real observed/forecast temperature; Heat
// Risk colors it by a single combined tier folding together thermal
// stress and modeled mortality risk (see combinedHeatRiskTier). The
// ward panel itself always shows every real value regardless of mode.
export function MapModeControl() {
  const { t } = useTranslation()
  const mapMode = useMapStore((s) => s.mapMode)
  const setMapMode = useMapStore((s) => s.setMapMode)

  return (
    <div className="segmented">
      {MODES.map((mode) => (
        <button
          key={mode}
          onClick={() => setMapMode(mode)}
          data-active={mapMode === mode}
          className="segmented-item"
        >
          {t(`mapModes.${mode}`)}
        </button>
      ))}
    </div>
  )
}
