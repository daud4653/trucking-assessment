import type { Notice } from '@/features/route-planning/api/schemas'
import { formatDateTime } from '@/lib/date-time'
import { formatPounds } from '@/lib/format'
import { usePlanSelection } from '../selection'
import styles from './PlanOverview.module.css'

const SEVERITY_ORDER: Record<Notice['severity'], number> = { critical: 0, warning: 1, info: 2 }

export function PlanOverview() {
  const { plan } = usePlanSelection()
  const notices = [...plan.notices].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  )
  return (
    <section className={styles.overview} aria-label="Plan summary">
      <p className={styles.trip}>
        <span>{plan.origin.label}</span>
        <span aria-hidden="true" className={styles.arrow}>
          →
        </span>
        <span className="visually-hidden">to</span>
        <span>{plan.destination.label}</span>
      </p>
      <p className={styles.meta}>
        Departs {formatDateTime(plan.departure_time)} · {formatPounds(plan.load_weight_lb)} load ·
        checkpoints every {plan.sampling_interval_miles} mi
      </p>
      {notices.length > 0 && (
        <ul className={styles.notices}>
          {notices.map((notice) => (
            <li key={notice.code} className={styles.notice} data-severity={notice.severity}>
              {notice.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
