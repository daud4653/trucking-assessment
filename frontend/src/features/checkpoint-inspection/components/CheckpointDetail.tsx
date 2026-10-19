import type { Checkpoint, MetricAssessment } from '@/features/route-planning/api/schemas'
import { formatAge, formatDateTime, formatTime } from '@/lib/date-time'
import { formatMeasurement, formatMiles, formatPounds } from '@/lib/format'
import { riskLabel } from '@/lib/risk'
import { RiskLabel } from '@/components/risk/RiskLabel'
import styles from './CheckpointDetail.module.css'

const METRIC_NAMES: Record<MetricAssessment['metric'], string> = {
  wind: 'Wind (sustained)',
  rain: 'Rain intensity',
  snow: 'Snow intensity',
}

const DATA_STATUS_TEXT: Record<Checkpoint['data_status'], string> = {
  complete: 'Complete forecast',
  partial: 'Partial forecast: classification is a minimum',
  unavailable: 'No forecast available: not assessed',
}

interface CheckpointDetailProps {
  checkpoint: Checkpoint
  loadWeightLb: number
  onClose: () => void
}

export function CheckpointDetail({ checkpoint, loadWeightLb, onClose }: CheckpointDetailProps) {
  const { weather } = checkpoint
  return (
    <article className={styles.detail} aria-label={`Checkpoint at mile ${checkpoint.distance_miles}`}>
      <div className={styles.titleRow}>
        <div>
          <p className={styles.title}>
            Mile <span className="numeric">{checkpoint.distance_miles.toFixed(1)}</span>
          </p>
          <p className={styles.subtitle}>
            ETA {formatDateTime(checkpoint.eta)} · represents mi{' '}
            <span className="numeric">
              {checkpoint.represents_from_miles.toFixed(1)}–{checkpoint.represents_to_miles.toFixed(1)}
            </span>
          </p>
        </div>
        <button type="button" className={styles.close} onClick={onClose} aria-label="Close checkpoint details">
          ×
        </button>
      </div>

      <div className={styles.verdict}>
        <RiskLabel level={checkpoint.risk_level} size="large" />
        <p className={styles.explanation}>{checkpoint.explanation}</p>
      </div>

      <table className={styles.metrics}>
        <caption className="visually-hidden">Forecast measurements and classifications</caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">Value</th>
            <th scope="col">Class</th>
          </tr>
        </thead>
        <tbody>
          {checkpoint.metrics.map((metric) => (
            <tr key={metric.metric} data-decisive={checkpoint.decisive_metrics.includes(metric.metric)}>
              <th scope="row">
                {METRIC_NAMES[metric.metric]}
                {metric.band && <span className={styles.band}>{metric.band}</span>}
              </th>
              <td className="numeric">
                {metric.invalid ? 'Invalid' : formatMeasurement(metric.value, metric.unit)}
              </td>
              <td>
                <RiskLabel level={metric.level} />
              </td>
            </tr>
          ))}
          {weather?.gust_mph != null && (
            <tr>
              <th scope="row">
                Gusts
                <span className={styles.band}>Shown for context; not classified</span>
              </th>
              <td className="numeric">{formatMeasurement(weather.gust_mph, 'mph')}</td>
              <td />
            </tr>
          )}
        </tbody>
      </table>

      {checkpoint.load_adjustment && (
        <p className={styles.adjustment}>
          Load rule applied: {formatPounds(loadWeightLb)} load raised wind from{' '}
          {riskLabel(checkpoint.load_adjustment.from_level)} to{' '}
          <strong>{riskLabel(checkpoint.load_adjustment.to_level)}</strong> (
          {checkpoint.load_adjustment.description}).
        </p>
      )}

      <dl className={styles.provenance}>
        <div>
          <dt>Data</dt>
          <dd data-status={checkpoint.data_status}>{DATA_STATUS_TEXT[checkpoint.data_status]}</dd>
        </div>
        {weather && (
          <>
            <div>
              <dt>Wind valid</dt>
              <dd>{formatTime(weather.valid_time)} (nearest forecast hour)</dd>
            </div>
            <div>
              <dt>Precip. hour</dt>
              <dd>ending {formatTime(weather.precipitation_window_end)}</dd>
            </div>
            <div>
              <dt>Retrieved</dt>
              <dd>{formatAge(weather.retrieved_at)}</dd>
            </div>
          </>
        )}
        <div>
          <dt>Location</dt>
          <dd className="numeric">
            {checkpoint.lat.toFixed(4)}, {checkpoint.lon.toFixed(4)} ·{' '}
            {formatMiles(checkpoint.distance_miles)} from origin
          </dd>
        </div>
      </dl>
    </article>
  )
}
