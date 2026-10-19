import type { Route } from '@/features/route-planning/api/schemas'
import { formatMiles } from '@/lib/format'
import { RISK_LABELS, RISK_LEVELS, riskColorVar } from '@/lib/risk'
import styles from './RiskStrip.module.css'

/** Share of route miles in each risk level, including unknown miles. */
export function RiskStrip({ summary }: { summary: Route['summary'] }) {
  const total = summary.total_miles
  const segments = [
    ...RISK_LEVELS.map((level) => ({
      key: level,
      label: RISK_LABELS[level],
      miles: summary.miles_by_level[level],
      color: riskColorVar(level),
    })),
    {
      key: 'unknown',
      label: 'Unknown',
      miles: summary.unknown_miles,
      color: riskColorVar(null),
    },
  ].filter((segment) => segment.miles > 0)

  const description = segments
    .map((segment) => `${segment.label} ${formatMiles(segment.miles)}`)
    .join(', ')

  return (
    <div className={styles.strip} role="img" aria-label={`Miles by risk: ${description}`}>
      {segments.map((segment) => (
        <span
          key={segment.key}
          className={segment.key === 'unknown' ? styles.unknown : styles.segment}
          style={{ flexGrow: segment.miles / total, background: segment.color }}
          title={`${segment.label}: ${formatMiles(segment.miles)}`}
        />
      ))}
    </div>
  )
}
