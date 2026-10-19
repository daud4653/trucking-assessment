import type { ReactNode } from 'react'
import styles from './TripEditor.module.css'

/** Keeps the trip form one click away once results are on screen. */
export function TripEditor({ children }: { children: ReactNode }) {
  return (
    <details className={styles.editor}>
      <summary className={styles.summary}>Change trip or departure</summary>
      {children}
    </details>
  )
}
