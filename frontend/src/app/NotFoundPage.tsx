import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <main style={{ padding: 'var(--space-8)', maxWidth: 560 }}>
      <h1 style={{ fontSize: 'var(--text-lg)', marginBottom: 'var(--space-2)' }}>Page not found</h1>
      <p>
        <Link to="/">Start a new route plan</Link>
      </p>
    </main>
  )
}
