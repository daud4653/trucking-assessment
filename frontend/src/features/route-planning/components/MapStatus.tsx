import { type PlanView, planErrorMessage } from '../plan-view'
import styles from './MapStatus.module.css'

/** Map overlay for every state without a loaded plan. */
export function MapStatus({ view, planning }: { view: PlanView; planning: boolean }) {
  if (planning) {
    return (
      <div className={styles.status} role="status">
        <p className={styles.title}>Planning routes</p>
        <p>Fetching truck routes, then forecasts at each checkpoint's arrival time.</p>
      </div>
    )
  }
  switch (view.status) {
    case 'empty':
      return (
        <div className={styles.status}>
          <p className={styles.title}>No trip yet</p>
          <p>
            Enter an origin, destination, departure time and load to compare up to three routes by
            forecast weather risk.
          </p>
        </div>
      )
    case 'loading':
      return (
        <div className={styles.status} role="status">
          <p className={styles.title}>Loading plan…</p>
        </div>
      )
    case 'error':
      return (
        <div className={styles.status} data-tone="error" role="alert">
          <p className={styles.title}>Plan unavailable</p>
          <p>{planErrorMessage(view.error)}</p>
          <button type="button" className={styles.button} onClick={view.retry}>
            Try again
          </button>
        </div>
      )
    case 'ready':
      return null
  }
}
