import type { CorridorForecast } from '@/features/route-planning/api/schemas'
import { formatPounds } from '@/lib/format'
import { RISK_LABELS, RISK_LEVELS, riskColorVar } from '@/lib/risk'
import type { HeatmapMetric } from '../heatmap'
import styles from './HeatmapLegend.module.css'

const TITLES: Record<HeatmapMetric, string> = {
  risk: 'Combined risk',
  wind: 'Sustained wind',
  rain: 'Rain intensity',
  snow: 'Snow intensity',
}

interface HeatmapLegendProps {
  metric: HeatmapMetric
  scales: CorridorForecast['scales'] | undefined
  loadWeightLb: number
}

export function HeatmapLegend({ metric, scales, loadWeightLb }: HeatmapLegendProps) {
  const bands = metric === 'risk' ? undefined : scales?.[metric]
  return (
    <figure className={styles.legend} aria-label={`${TITLES[metric]} legend`}>
      <figcaption className={styles.title}>
        {TITLES[metric]}
        {metric === 'risk' && (
          <span className={styles.subtitle}>Load-adjusted for {formatPounds(loadWeightLb)}</span>
        )}
      </figcaption>
      <ul>
        {RISK_LEVELS.map((level) => (
          <li key={level}>
            <span className={styles.swatch} style={{ background: riskColorVar(level) }} />
            <span>{RISK_LABELS[level]}</span>
            {bands && (
              <span className={styles.band}>
                {bands.find((band) => band.level === level)?.band}
              </span>
            )}
          </li>
        ))}
        <li>
          <span className={styles.swatchUnknown} />
          <span>No forecast</span>
        </li>
      </ul>
    </figure>
  )
}
