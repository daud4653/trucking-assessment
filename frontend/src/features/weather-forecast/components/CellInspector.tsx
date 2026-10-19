import { RiskLabel } from '@/components/risk/RiskLabel'
import type { CorridorFrame } from '@/features/route-planning/api/schemas'
import { formatDateTime } from '@/lib/date-time'
import { formatMeasurement } from '@/lib/format'
import { levelFromIndex } from '@/lib/risk'
import styles from './CellInspector.module.css'

interface CellInspectorProps {
  frame: CorridorFrame
  cellIndex: number
  bounds: [number, number, number, number]
  onClose: () => void
}

export function CellInspector({ frame, cellIndex, bounds, onClose }: CellInspectorProps) {
  const [west, south, east, north] = bounds
  const rows = [
    { name: 'Wind', value: frame.wind_mph[cellIndex] ?? null, unit: 'mph', level: frame.wind_level[cellIndex] },
    { name: 'Rain', value: frame.rain_in_per_hr[cellIndex] ?? null, unit: 'in/hr', level: frame.rain_level[cellIndex] },
    { name: 'Snow', value: frame.snow_in_per_hr[cellIndex] ?? null, unit: 'in/hr', level: frame.snow_level[cellIndex] },
  ]
  return (
    <aside className={styles.inspector} aria-label="Corridor cell forecast">
      <div className={styles.header}>
        <div>
          <p className={styles.title}>Corridor cell</p>
          <p className={styles.meta}>
            {formatDateTime(frame.valid_time)} ·{' '}
            <span className="numeric">
              {((south + north) / 2).toFixed(2)}, {((west + east) / 2).toFixed(2)}
            </span>
          </p>
        </div>
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close cell forecast">
          ×
        </button>
      </div>
      <dl className={styles.values}>
        <div>
          <dt>Combined (load-adjusted)</dt>
          <dd>
            <RiskLabel level={levelFromIndex(frame.risk[cellIndex])} />
          </dd>
        </div>
        {rows.map((row) => (
          <div key={row.name}>
            <dt>{row.name}</dt>
            <dd>
              <span className="numeric">{formatMeasurement(row.value, row.unit)}</span>
              <RiskLabel level={levelFromIndex(row.level)} />
            </dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}
