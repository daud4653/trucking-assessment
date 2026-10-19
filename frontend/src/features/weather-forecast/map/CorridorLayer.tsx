import type { ExpressionSpecification } from 'maplibre-gl'
import { useEffect, useMemo } from 'react'
import { useGeoJsonSource, useLayer, useLayerClick } from '@/components/map/hooks'
import { useMap } from '@/components/map/map-context'
import { Z_LAYERS } from '@/components/map/MapView'
import type { CorridorForecast } from '@/features/route-planning/api/schemas'
import { resolveRiskColors } from '@/lib/risk'
import { type HeatmapMetric, levelsFor } from '../heatmap'

const SOURCE = 'corridor'
const LAYER = 'corridor-fill'
const UNKNOWN = -1

interface CorridorLayerProps {
  forecast: CorridorForecast
  frameIndex: number
  metric: HeatmapMetric
  visible: boolean
  onInspect: (cellIndex: number) => void
}

/**
 * Corridor cells drawn as flat squares at each forecast sample: no
 * interpolation, so missing data stays visibly missing instead of being
 * smoothed into neighbouring values. The slider changes only feature state,
 * which avoids re-tiling the source on every step.
 */
export function CorridorLayer({ forecast, frameIndex, metric, visible, onInspect }: CorridorLayerProps) {
  const map = useMap()
  const colors = useMemo(resolveRiskColors, [])
  const cells = useMemo(() => cellFeatures(forecast), [forecast])
  useGeoJsonSource(SOURCE, cells)

  const level: ExpressionSpecification = ['coalesce', ['feature-state', 'level'], UNKNOWN]
  useLayer(
    {
      id: LAYER,
      type: 'fill',
      source: SOURCE,
      paint: {
        'fill-color': [
          'match',
          level,
          0, colors.low,
          1, colors.moderate,
          2, colors.high,
          3, colors.severe,
          4, colors.no_travel,
          colors.unknown,
        ],
        'fill-opacity': ['case', ['==', level, UNKNOWN], 0.22, ['==', level, 0], 0.22, 0.5],
        'fill-antialias': false,
      },
    },
    Z_LAYERS.heatmap,
  )

  useEffect(() => {
    const frame = forecast.frames[frameIndex]
    if (!frame) return
    const levels = levelsFor(frame, metric)
    for (let id = 0; id < forecast.cells.length; id++) {
      map.setFeatureState({ source: SOURCE, id }, { level: levels[id] ?? UNKNOWN })
    }
  }, [map, forecast, frameIndex, metric])

  useEffect(() => {
    map.setLayoutProperty(LAYER, 'visibility', visible ? 'visible' : 'none')
  }, [map, visible])

  useLayerClick(LAYER, (event) => {
    const id = event.features?.[0]?.id
    if (typeof id === 'number') onInspect(id)
  })
  return null
}

function cellFeatures(forecast: CorridorForecast): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: forecast.cells.map(([west, south, east, north], id) => ({
      type: 'Feature',
      id,
      properties: {},
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
          ],
        ],
      },
    })),
  }
}
