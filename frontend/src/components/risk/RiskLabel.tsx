import type { RiskLevel } from '@/features/route-planning/api/schemas'
import { riskColorVar, riskLabel } from '@/lib/risk'
import styles from './RiskLabel.module.css'

interface RiskLabelProps {
  level: RiskLevel | null
  size?: 'regular' | 'large'
}

/** Risk level as text with a square color key; unknown is shown hollow. */
export function RiskLabel({ level, size = 'regular' }: RiskLabelProps) {
  return (
    <span className={styles.label} data-size={size} data-unknown={level === null}>
      <span className={styles.swatch} style={{ background: riskColorVar(level) }} aria-hidden="true" />
      {riskLabel(level)}
    </span>
  )
}
