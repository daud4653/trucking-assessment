import type { Checkpoint } from '@/features/route-planning/api/schemas'
import { formatTime } from '@/lib/date-time'
import { formatMeasurement } from '@/lib/format'
import { RiskLabel } from '@/components/risk/RiskLabel'
import styles from './CheckpointList.module.css'

interface CheckpointListProps {
  checkpoints: Checkpoint[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export function CheckpointList({ checkpoints, selectedId, onSelect }: CheckpointListProps) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Checkpoints along the selected route</caption>
      <thead>
        <tr>
          <th scope="col">Mile</th>
          <th scope="col">ETA</th>
          <th scope="col">Risk</th>
          <th scope="col">Wind</th>
          <th scope="col">Rain</th>
          <th scope="col">Snow</th>
        </tr>
      </thead>
      <tbody>
        {checkpoints.map((checkpoint) => {
          const selected = checkpoint.id === selectedId
          return (
            <tr key={checkpoint.id} data-selected={selected}>
              <td>
                <button
                  type="button"
                  className={`${styles.select} numeric`}
                  aria-pressed={selected}
                  aria-label={`Mile ${checkpoint.distance_miles.toFixed(1)}, ${checkpoint.risk_level ?? 'unknown'} risk`}
                  onClick={() => onSelect(checkpoint.id)}
                >
                  {checkpoint.distance_miles.toFixed(0)}
                </button>
              </td>
              <td className="numeric">{formatTime(checkpoint.eta)}</td>
              <td>
                <RiskLabel level={checkpoint.risk_level} />
              </td>
              <td className="numeric">{shortValue(checkpoint.weather?.wind_mph, 'mph')}</td>
              <td className="numeric">{shortValue(checkpoint.weather?.rain_in_per_hr, 'in/hr')}</td>
              <td className="numeric">{shortValue(checkpoint.weather?.snow_in_per_hr, 'in/hr')}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function shortValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return '—'
  return formatMeasurement(value, unit).split(' ')[0] ?? '—'
}
