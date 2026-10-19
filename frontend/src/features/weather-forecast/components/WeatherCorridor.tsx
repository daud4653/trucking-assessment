import { usePlanSelection } from '@/features/route-comparison/selection'
import type { CorridorForecast } from '@/features/route-planning/api/schemas'
import { formatTime } from '@/lib/date-time'
import { useCorridorView } from '../corridor-view'
import { offsetOf } from '../heatmap'
import { useCorridorForecast } from '../hooks/useCorridorForecast'
import { CorridorLayer } from '../map/CorridorLayer'
import { CellInspector } from './CellInspector'
import { type CorridorState, ForecastTimeline } from './ForecastTimeline'
import { HeatmapLegend } from './HeatmapLegend'

/** Map layer half: rendered inside the loaded map. */
export function WeatherCorridorLayer() {
  const { plan } = usePlanSelection()
  const view = useCorridorView()
  const { data } = useCorridorForecast(plan.id)
  if (!data) return null
  return (
    <CorridorLayer
      forecast={data}
      frameIndex={view.offset}
      metric={view.metric}
      visible={view.visible}
      onInspect={view.inspectCell}
    />
  )
}

/** Overlay half: legend, cell inspector and the forecast timeline. */
export function WeatherCorridorOverlays() {
  const { plan, selectedRoute } = usePlanSelection()
  const view = useCorridorView()
  const query = useCorridorForecast(plan.id)
  const forecast = query.data
  const frame = forecast?.frames[view.offset]
  const cellBounds = view.inspectedCell === null ? undefined : forecast?.cells[view.inspectedCell]

  const corridor = toCorridorState(forecast, query.isError, () => void query.refetch())

  const base = forecast?.base_time ?? plan.departure_time
  const tripWindow = {
    start: offsetOf(base, plan.departure_time),
    end: offsetOf(base, selectedRoute.arrival_time),
    label: `Shaded: ${selectedRoute.label} on the road until ${formatTime(selectedRoute.arrival_time)}`,
  }

  return (
    <>
      {view.visible && (
        <HeatmapLegend metric={view.metric} scales={forecast?.scales} loadWeightLb={plan.load_weight_lb} />
      )}
      {frame && cellBounds && view.inspectedCell !== null && (
        <CellInspector
          frame={frame}
          cellIndex={view.inspectedCell}
          bounds={cellBounds}
          onClose={() => view.inspectCell(null)}
        />
      )}
      <ForecastTimeline
        corridor={corridor}
        offset={view.offset}
        onOffsetChange={view.setOffset}
        metric={view.metric}
        onMetricChange={view.setMetric}
        visible={view.visible}
        onVisibleChange={view.setVisible}
        tripWindow={tripWindow}
      />
    </>
  )
}

function toCorridorState(
  forecast: CorridorForecast | undefined,
  failed: boolean,
  retry: () => void,
): CorridorState {
  if (forecast) return { status: 'ready', forecast }
  if (failed) return { status: 'error', message: 'Corridor forecast unavailable.', retry }
  return { status: 'loading' }
}
