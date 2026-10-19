import type { Route } from '@/features/route-planning/api/schemas'
import { formatDuration, formatTime } from '@/lib/date-time'
import { formatMiles, formatPercent } from '@/lib/format'
import { SCREENING_LABELS, riskLabel } from '@/lib/risk'
import { usePlanSelection } from '../selection'
import { RiskStrip } from './RiskStrip'
import styles from './RouteComparison.module.css'

export function RouteComparison() {
  const { plan, selectedRoute, selectRoute } = usePlanSelection()
  const ranked = [...plan.routes].sort((a, b) => a.rank - b.rank)
  const allProhibited = plan.routes.every((route) => route.screening === 'no_travel')

  return (
    <section className={styles.section} aria-labelledby="route-comparison-heading">
      <div className={styles.heading}>
        <h2 id="route-comparison-heading" className="eyebrow">
          Route options
        </h2>
        <span className={styles.count}>
          {plan.routes.length} of 3 · risk first, then time
        </span>
      </div>
      <ul className={styles.list}>
        {ranked.map((route) => (
          <li key={route.id}>
            <RouteOption
              route={route}
              selected={route.id === selectedRoute.id}
              allProhibited={allProhibited}
              onSelect={() => selectRoute(route.id)}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

interface RouteOptionProps {
  route: Route
  selected: boolean
  allProhibited: boolean
  onSelect: () => void
}

function RouteOption({ route, selected, allProhibited, onSelect }: RouteOptionProps) {
  const { summary } = route
  return (
    <button
      type="button"
      className={styles.option}
      data-selected={selected}
      data-screening={route.screening}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className={styles.optionHeader}>
        <span className={styles.rank} aria-label={`Rank ${route.rank}`}>
          {route.rank}
        </span>
        <span className={styles.label}>{route.label}</span>
        <StatusText route={route} allProhibited={allProhibited} />
      </span>

      <dl className={styles.metrics}>
        <Metric term="Distance" value={formatMiles(route.distance_miles)} />
        <Metric term="Drive time" value={formatDuration(route.duration_seconds)} />
        <Metric term="Arrive" value={formatTime(route.arrival_time)} />
        <Metric
          term="Severe+ mi"
          value={summary.severe_or_worse_miles.toFixed(1)}
          emphasis={summary.severe_or_worse_miles > 0}
        />
        <Metric term="High mi" value={summary.high_miles.toFixed(1)} emphasis={summary.high_miles > 0} />
        <Metric
          term="Avg risk"
          value={summary.average_risk === null ? '—' : summary.average_risk.toFixed(2)}
        />
      </dl>

      <RiskStrip summary={summary} />

      <span className={styles.footnote}>
        <span>
          Peak <strong>{riskLabel(summary.peak_level)}</strong>
        </span>
        <span data-warning={summary.is_uncertain}>
          Forecast coverage {formatPercent(summary.coverage_ratio)}
        </span>
        {route.eta_method === 'proportional' && <span>ETAs approximate</span>}
      </span>

      {selected && <span className={styles.explanation}>{route.ranking_explanation}</span>}
    </button>
  )
}

function StatusText({ route, allProhibited }: { route: Route; allProhibited: boolean }) {
  if (route.screening === 'no_travel') {
    return <span className={styles.statusCritical}>No Travel segment</span>
  }
  if (route.is_recommended && !allProhibited) {
    return (
      <span className={styles.statusRecommended}>
        {route.screening === 'uncertain' ? 'Best ranked · uncertain' : 'Recommended'}
      </span>
    )
  }
  if (route.screening === 'uncertain') {
    return <span className={styles.statusWarning}>{SCREENING_LABELS.uncertain}</span>
  }
  return null
}

function Metric({ term, value, emphasis = false }: { term: string; value: string; emphasis?: boolean }) {
  return (
    <div className={styles.metric}>
      <dt>{term}</dt>
      <dd className="numeric" data-emphasis={emphasis}>
        {value}
      </dd>
    </div>
  )
}
