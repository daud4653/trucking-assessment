import 'maplibre-gl/dist/maplibre-gl.css'
import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { MapContext } from './map-context'
import styles from './MapView.module.css'

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const INITIAL_VIEW = { center: [-95.5, 38.5] as [number, number], zoom: 3.6 }

/** Empty layers that fix draw order for feature layers added later. */
export const Z_LAYERS = {
  heatmap: 'z-heatmap',
  routes: 'z-routes',
  checkpoints: 'z-checkpoints',
} as const

type MapState =
  | { status: 'loading' }
  | { status: 'ready'; map: MapLibreMap }
  | { status: 'failed'; message: string }

interface MapViewProps {
  label: string
  children?: ReactNode
  overlay?: ReactNode
}

export function MapView({ label, children, overlay }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<MapState>({ status: 'loading' })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    let map: MapLibreMap
    try {
      map = new maplibregl.Map({
        container,
        style: STYLE_URL,
        ...INITIAL_VIEW,
        attributionControl: { compact: true },
        dragRotate: false,
        pitchWithRotate: false,
      })
    } catch {
      setState({
        status: 'failed',
        message: 'The map could not start (WebGL unavailable). Route details remain available.',
      })
      return
    }
    map.touchZoomRotate.disableRotation()
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }), 'bottom-right')
    map.on('load', () => {
      addOrderingLayers(map)
      setState({ status: 'ready', map })
    })
    map.on('error', (event) => {
      const error: unknown = event.error
      if (!map.loaded() && error instanceof Error && error.message.includes('style')) {
        setState({ status: 'failed', message: 'Base map tiles could not be loaded.' })
      }
    })
    return () => map.remove()
  }, [])

  return (
    <div className={styles.root}>
      <div ref={containerRef} className={styles.canvas} role="region" aria-label={label} />
      {state.status === 'failed' && <p className={styles.failure}>{state.message}</p>}
      {state.status === 'ready' && <MapContext value={state.map}>{children}</MapContext>}
      {overlay}
    </div>
  )
}

function addOrderingLayers(map: MapLibreMap) {
  const firstSymbol = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id
  map.addSource('z-anchors', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  const anchor = (id: string, before?: string) =>
    map.addLayer({ id, type: 'line', source: 'z-anchors', layout: { visibility: 'none' } }, before)
  anchor(Z_LAYERS.heatmap, firstSymbol)
  anchor(Z_LAYERS.routes, firstSymbol)
  anchor(Z_LAYERS.checkpoints)
}
