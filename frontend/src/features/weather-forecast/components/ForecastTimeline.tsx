import { SegmentedControl } from '@/components/forms/SegmentedControl'
import type { CorridorForecast } from '@/features/route-planning/api/schemas'
import { formatAge, formatDateTime } from '@/lib/date-time'
import { formatPercent } from '@/lib/format'
import { HEATMAP_METRICS, type HeatmapMetric } from '../heatmap'
import styles from './ForecastTimeline.module.css'

export const MAX_OFFSET_HOURS = 48

export type CorridorState =
  | { status: 'loading' }
  | { status: 'error'; message: string; retry: () => void }
  | { status: 'ready'; forecast: CorridorForecast }

interface ForecastTimelineProps {
  corridor: CorridorState
  offset: number
  onOffsetChange: (offset: number) => void
  metric: HeatmapMetric
  onMetricChange: (metric: HeatmapMetric) => void
  visible: boolean
  onVisibleChange: (visible: boolean) => void
  tripWindow: { start: number; end: number; label: string }
}

export function ForecastTimeline(props: ForecastTimelineProps) {
  const { corridor, offset, onOffsetChange, visible, onVisibleChange, tripWindow } = props
  const frame = corridor.status === 'ready' ? corridor.forecast.frames[offset] : undefined
  const disabled = corridor.status !== 'ready'
  const startPct = (Math.max(0, tripWindow.start) / MAX_OFFSET_HOURS) * 100
  const endPct = (Math.min(MAX_OFFSET_HOURS, tripWindow.end) / MAX_OFFSET_HOURS) * 100

  return (
    <section className={styles.timeline} aria-label="Corridor weather forecast">
      <div className={styles.controls}>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={visible}
            onChange={(event) => onVisibleChange(event.target.checked)}
          />
          Weather corridor
        </label>
        <SegmentedControl
          name="heatmap-metric"
          legend="Heatmap layer"
          hideLegend
          options={HEATMAP_METRICS}
          value={props.metric}
          onChange={props.onMetricChange}
        />
      </div>

      <div className={styles.sliderRow}>
        <label htmlFor="forecast-offset" className={styles.offset}>
          <span className="numeric">+{String(offset).padStart(2, '0')} h</span>
        </label>
        <div className={styles.track}>
          {endPct > startPct && (
            <span
              className={styles.tripBand}
              style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
              title={tripWindow.label}
              aria-hidden="true"
            />
          )}
          <input
            id="forecast-offset"
            type="range"
            min={0}
            max={MAX_OFFSET_HOURS}
            step={1}
            value={offset}
            disabled={disabled}
            onChange={(event) => onOffsetChange(Number(event.target.value))}
            aria-valuetext={frame ? `${offset} hours after departure, ${formatDateTime(frame.valid_time)}` : `${offset} hours after departure`}
          />
        </div>
        <output htmlFor="forecast-offset" className={styles.validTime}>
          {frame ? formatDateTime(frame.valid_time) : '—'}
        </output>
      </div>

      <p className={styles.status} aria-live="polite">
        <StatusLine corridor={corridor} tripLabel={tripWindow.label} />
      </p>
    </section>
  )
}

function StatusLine({ corridor, tripLabel }: { corridor: CorridorState; tripLabel: string }) {
  switch (corridor.status) {
    case 'loading':
      return <>Loading 48-hour corridor forecast…</>
    case 'error':
      return (
        <>
          <span className={styles.error}>{corridor.message}</span>{' '}
          <button type="button" className={styles.retry} onClick={corridor.retry}>
            Retry
          </button>
        </>
      )
    case 'ready': {
      const { forecast } = corridor
      return (
        <>
          Hourly forecast at departure + offset; precipitation is the hour ending at the shown time.{' '}
          {tripLabel}. Coverage {formatPercent(forecast.coverage_ratio)}
          {forecast.retrieved_at && <> · retrieved {formatAge(forecast.retrieved_at)}</>}.
        </>
      )
    }
  }
}
