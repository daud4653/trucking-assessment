import { useRef } from 'react'
import { Link } from 'react-router'
import { MethodologyDialog } from './MethodologyDialog'
import styles from './TopBar.module.css'

export function TopBar({ title }: { title: string }) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  return (
    <header className={styles.bar}>
      <Link to="/" className={styles.brand} aria-label="Weather-Aware Truck Routing, new plan">
        <span className={styles.mark} aria-hidden="true" />
        <span className={styles.name}>Weather-Aware Truck Routing</span>
        <span className={styles.shortName} aria-hidden="true">
          Truck Weather
        </span>
      </Link>
      <h1 className={styles.title}>{title}</h1>
      <nav className={styles.nav} aria-label="Workspace">
        <Link to="/" className={styles.link}>
          New plan
        </Link>
        <button type="button" className={styles.link} onClick={() => dialogRef.current?.showModal()}>
          Methodology
        </button>
      </nav>
      <MethodologyDialog ref={dialogRef} />
    </header>
  )
}
