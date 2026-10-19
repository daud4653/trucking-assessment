import type {
  GeoJSONSource,
  LayerSpecification,
  MapLayerMouseEvent,
  Map as MapLibreMap,
} from 'maplibre-gl'
import { useEffect, useRef } from 'react'
import { useMap } from './map-context'

type GeoJsonData = GeoJSON.FeatureCollection

/**
 * Adds a GeoJSON source once and pushes data changes with setData, so the
 * map never re-creates sources or layers on React re-renders.
 */
export function useGeoJsonSource(id: string, data: GeoJsonData): void {
  const map = useMap()
  const latest = useRef(data)
  latest.current = data

  useEffect(() => {
    map.addSource(id, { type: 'geojson', data: latest.current })
    return () => {
      removeSource(map, id)
    }
  }, [map, id])

  useEffect(() => {
    const source = map.getSource<GeoJSONSource>(id)
    source?.setData(data)
  }, [map, id, data])
}

/** Adds a layer for the component's lifetime, positioned before `beforeId`. */
export function useLayer(layer: LayerSpecification, beforeId?: string): void {
  const map = useMap()
  const spec = useRef(layer)

  useEffect(() => {
    map.addLayer(spec.current, beforeId)
    const id = spec.current.id
    return () => {
      if (map.getLayer(id)) map.removeLayer(id)
    }
  }, [map, beforeId])
}

/** Click and hover-cursor handling for an interactive layer. */
export function useLayerClick(layerId: string, onClick: (event: MapLayerMouseEvent) => void): void {
  const map = useMap()
  const handler = useRef(onClick)
  handler.current = onClick

  useEffect(() => {
    const click = (event: MapLayerMouseEvent) => handler.current(event)
    const enter = () => (map.getCanvas().style.cursor = 'pointer')
    const leave = () => (map.getCanvas().style.cursor = '')
    map.on('click', layerId, click)
    map.on('mouseenter', layerId, enter)
    map.on('mouseleave', layerId, leave)
    return () => {
      map.off('click', layerId, click)
      map.off('mouseenter', layerId, enter)
      map.off('mouseleave', layerId, leave)
    }
  }, [map, layerId])
}

function removeSource(map: MapLibreMap, id: string) {
  if (!map.getSource(id)) return
  for (const layer of map.getStyle().layers) {
    if ('source' in layer && layer.source === id) map.removeLayer(layer.id)
  }
  map.removeSource(id)
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}
