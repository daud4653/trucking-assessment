import type { ReactNode } from 'react'
import { TopBar } from './TopBar'
import styles from './WorkspaceLayout.module.css'

interface WorkspaceLayoutProps {
  title: string
  sidebar: ReactNode
  map: ReactNode
  details: ReactNode
}

export function WorkspaceLayout({ title, sidebar, map, details }: WorkspaceLayoutProps) {
  return (
    <div className={styles.shell}>
      <TopBar title={title} />
      <div className={styles.workspace} data-has-details={details !== null}>
        <aside className={styles.sidebar} aria-label="Trip planning and route comparison">
          {sidebar}
        </aside>
        <main className={styles.map}>{map}</main>
        {details !== null && (
          <aside className={styles.details} aria-label="Checkpoint details">
            {details}
          </aside>
        )}
      </div>
    </div>
  )
}
