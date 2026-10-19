import type { ExpressionSpecification } from 'maplibre-gl'
import { useEffect, useMemo } from 'react'
import { prefersReducedMotion, useGeoJsonSource, useLayer, useLayerClick } from '@/components/map/hooks'
import { useMap } from '@/components/map/map-context'
import { Z_LAYERS } from '@/components/map/MapView'
import type { RoutePlan } from '@/features/route-planning/api/schemas'
import { resolveRiskColors } from '@/lib/risk'
import { usePlanSelection } from '../selection'
import { splitRouteByCheckpoints } from '../utils/segments'

const SOURCES = { routes: 'routes', segments: 'route-risk', checkpoints: 'checkpoints' }

export function RouteLayers() {
  const { plan, selectedRoute, selectedCheckpoint, selectRoute, selectCheckpoint } =
    usePlanSelection()
  const colors = useMemo(resolveRiskColors, [])
  const levelColor: ExpressionSpecification = [
    'match',
    ['get', 'level'],
    'low', colors.low,
    'moderate', colors.moderate,
    'high', colors.high,
    'severe', colors.severe,
    'no_travel', colors.no_travel,
    colors.unknown,
  ]

  const routes = useMemo(() => routeFeatures(plan, selectedRoute.id), [plan, selectedRoute.id])
  const segments = useMemo(
    () => segmentFeatures(selectedRoute),
    [selectedRoute],
  )
  const checkpoints = useMemo(
    () => checkpointFeatures(selectedRoute, selectedCheckpoint?.id ?? null),
    [selectedRoute, selectedCheckpoint?.id],
  )

  useGeoJsonSource(SOURCES.routes, routes)
  useGeoJsonSource(SOURCES.segments, segments)
  useGeoJsonSource(SOURCES.checkpoints, checkpoints)

  useLayer(
    {
      id: 'routes-alternative',
      type: 'line',
      source: SOURCES.routes,
      filter: ['==', ['get', 'selected'], false],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#6f777b', 'line-width': 3.5, 'line-opacity': 0.75 },
    },
    Z_LAYERS.routes,
  )
  useLayer(
    {
      id: 'routes-alternative-hit',
      type: 'line',
      source: SOURCES.routes,
      filter: ['==', ['get', 'selected'], false],
      paint: { 'line-color': '#000', 'line-width': 16, 'line-opacity': 0 },
    },
    Z_LAYERS.routes,
  )
  useLayer(
    {
      id: 'routes-selected-casing',
      type: 'line',
      source: SOURCES.routes,
      filter: ['==', ['get', 'selected'], true],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#1d2427', 'line-width': 9 },
    },
    Z_LAYERS.routes,
  )
  useLayer(
    {
      id: 'route-risk',
      type: 'line',
      source: SOURCES.segments,
      filter: ['!=', ['get', 'level'], 'unknown'],
      layout: { 'line-join': 'round', 'line-cap': 'butt' },
      paint: { 'line-color': levelColor, 'line-width': 5 },
    },
    Z_LAYERS.routes,
  )
  useLayer(
    {
      id: 'route-risk-unknown',
      type: 'line',
      source: SOURCES.segments,
      filter: ['==', ['get', 'level'], 'unknown'],
      paint: { 'line-color': '#ffffff', 'line-width': 5, 'line-dasharray': [1.2, 1] },
    },
    Z_LAYERS.routes,
  )
  useLayer(
    {
      id: 'checkpoints',
      type: 'circle',
      source: SOURCES.checkpoints,
      paint: {
        'circle-radius': ['case', ['get', 'selected'], 8, 5],
        'circle-color': ['case', ['==', ['get', 'level'], 'unknown'], '#ffffff', levelColor],
        'circle-stroke-color': [
          'case',
          ['get', 'selected'], '#1d2427',
          ['==', ['get', 'level'], 'unknown'], colors.unknown,
          '#ffffff',
        ],
        'circle-stroke-width': ['case', ['get', 'selected'], 3, 1.5],
      },
    },
    Z_LAYERS.checkpoints,
  )

  useLayerClick('routes-alternative-hit', (event) => {
    const id: unknown = event.features?.[0]?.properties.id
    if (typeof id === 'string') selectRoute(id)
  })
  useLayerClick('checkpoints', (event) => {
    const id: unknown = event.features?.[0]?.properties.id
    if (typeof id === 'string') selectCheckpoint(id)
  })

  useFitToPlan(plan)
  useRevealCheckpoint(selectedCheckpoint ? [selectedCheckpoint.lon, selectedCheckpoint.lat] : null)
  return null
}

function useFitToPlan(plan: RoutePlan) {
  const map = useMap()
  useEffect(() => {
    const bounds = boundsOf(plan)
    map.fitBounds(bounds, {
      padding: fitPadding(),
      duration: prefersReducedMotion() ? 0 : 600,
    })
  }, [map, plan])
}

function useRevealCheckpoint(position: [number, number] | null) {
  const map = useMap()
  const lon = position?.[0]
  const lat = position?.[1]
  useEffect(() => {
    if (lon === undefined || lat === undefined) return
    if (map.getBounds().contains([lon, lat])) return
    map.easeTo({ center: [lon, lat], duration: prefersReducedMotion() ? 0 : 400 })
  }, [map, lon, lat])
}

function fitPadding() {
  // On wide layouts the forecast timeline overlays the bottom of the map.
  const compact = window.matchMedia('(max-width: 640px)').matches
  return compact
    ? { top: 32, bottom: 32, left: 24, right: 24 }
    : { top: 48, bottom: 220, left: 200, right: 64 }
}

function boundsOf(plan: RoutePlan): [[number, number], [number, number]] {
  let west = 180
  let south = 90
  let east = -180
  let north = -90
  for (const route of plan.routes) {
    for (const [lon, lat] of route.geometry.coordinates) {
      west = Math.min(west, lon)
      east = Math.max(east, lon)
      south = Math.min(south, lat)
      north = Math.max(north, lat)
    }
  }
  return [
    [west, south],
    [east, north],
  ]
}

function routeFeatures(plan: RoutePlan, selectedId: string): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: plan.routes.map((route) => ({
      type: 'Feature',
      properties: { id: route.id, selected: route.id === selectedId },
      geometry: route.geometry,
    })),
  }
}

function segmentFeatures(route: RoutePlan['routes'][number]): GeoJSON.FeatureCollection {
  const segments = splitRouteByCheckpoints(
    route.geometry.coordinates,
    route.distance_miles,
    route.checkpoints,
  )
  return {
    type: 'FeatureCollection',
    features: segments.map((segment) => ({
      type: 'Feature',
      properties: { id: segment.checkpointId, level: segment.level ?? 'unknown' },
      geometry: { type: 'LineString', coordinates: segment.coordinates },
    })),
  }
}

function checkpointFeatures(
  route: RoutePlan['routes'][number],
  selectedId: string | null,
): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: route.checkpoints.map((checkpoint) => ({
      type: 'Feature',
      properties: {
        id: checkpoint.id,
        level: checkpoint.risk_level ?? 'unknown',
        selected: checkpoint.id === selectedId,
      },
      geometry: { type: 'Point', coordinates: [checkpoint.lon, checkpoint.lat] },
    })),
  }
}
