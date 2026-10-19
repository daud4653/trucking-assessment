import type { Map as MapLibreMap } from 'maplibre-gl'
import { createContext, use } from 'react'

export const MapContext = createContext<MapLibreMap | null>(null)

export function useMap(): MapLibreMap {
  const map = use(MapContext)
  if (map === null) throw new Error('useMap must be used inside a loaded MapView')
  return map
}
