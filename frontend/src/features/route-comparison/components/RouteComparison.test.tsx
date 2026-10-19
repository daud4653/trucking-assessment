import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CheckpointPanel } from '@/features/checkpoint-inspection/components/CheckpointPanel'
import { checkpoint, plan, route } from '@/test/fixtures'
import { renderWithProviders } from '@/test/render'
import { RouteComparison } from './RouteComparison'

const prohibited = route({
  id: 'route-2',
  label: 'Route B',
  rank: 2,
  screening: 'no_travel',
  is_recommended: false,
  ranking_explanation: 'Ranked second: this route contains a No Travel segment.',
  summary: {
    ...route().summary,
    miles_by_level: { low: 20, moderate: 0, high: 0, severe: 0, no_travel: 5 },
    severe_or_worse_miles: 5,
    peak_level: 'no_travel',
    has_no_travel: true,
  },
  checkpoints: [
    checkpoint({ id: 'route-2-cp-0' }),
    checkpoint({
      id: 'route-2-cp-1',
      sequence: 1,
      distance_miles: 25,
      risk_level: 'no_travel',
      explanation: 'No Travel: wind is 50 mph and the load is 42,000 lb, triggering the heavy-load severe-wind rule.',
      load_adjustment: {
        rule: 'heavy_load_severe_wind',
        description: 'heavy-load severe-wind rule (45 to below 55 mph wind with load over 30,000 lb)',
        from_level: 'severe',
        to_level: 'no_travel',
      },
    }),
  ],
})

const uncertain = route({
  id: 'route-3',
  label: 'Route C',
  rank: 3,
  screening: 'uncertain',
  is_recommended: false,
  summary: { ...route().summary, coverage_ratio: 0.6, unknown_miles: 10, is_uncertain: true },
})

const testPlan = plan({ routes: [route(), prohibited, uncertain] })

function setup() {
  renderWithProviders(
    <>
      <RouteComparison />
      <CheckpointPanel />
    </>,
    { plan: testPlan },
  )
  return userEvent.setup()
}

describe('RouteComparison', () => {
  it('lists routes by rank with the recommended route selected', () => {
    setup()
    const buttons = screen.getAllByRole('button', { pressed: true })
    expect(buttons[0]).toHaveTextContent('Route A')
    expect(screen.getByText('Recommended')).toBeInTheDocument()
    expect(screen.getByText('No Travel segment')).toBeInTheDocument()
    expect(screen.getByText('Uncertain: incomplete forecast')).toBeInTheDocument()
    expect(screen.getByText('Forecast coverage 60%')).toHaveAttribute('data-warning', 'true')
  })

  it('selecting a route updates the checkpoint panel and explanation', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /Rank 2 Route B/ }))
    expect(screen.getByRole('button', { name: /Rank 2 Route B/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('heading', { name: 'Checkpoints · Route B' })).toBeInTheDocument()
    expect(screen.getByText('Ranked second: this route contains a No Travel segment.')).toBeInTheDocument()
  })

  it('checkpoint details show measurements and the load rule that applied', async () => {
    const user = setup()
    await user.click(screen.getByRole('button', { name: /Rank 2 Route B/ }))
    await user.click(screen.getByRole('button', { name: 'Mile 25.0, no_travel risk' }))

    const detail = screen.getByRole('article', { name: /Checkpoint at mile 25/ })
    expect(within(detail).getByText(/triggering the heavy-load severe-wind rule/)).toBeInTheDocument()
    expect(within(detail).getByText(/Load rule applied/)).toHaveTextContent('raised wind from Severe to No Travel')

    await user.click(within(detail).getByRole('button', { name: 'Close checkpoint details' }))
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('unknown checkpoints are labelled unknown, never low', async () => {
    const missing = checkpoint({
      id: 'route-1-cp-1',
      sequence: 1,
      distance_miles: 25,
      risk_level: null,
      data_status: 'unavailable',
      weather: null,
      decisive_metrics: [],
      metrics: (['wind', 'rain', 'snow'] as const).map((metric) => ({
        metric,
        value: null,
        unit: metric === 'wind' ? 'mph' : 'in/hr',
        level: null,
        band: null,
        invalid: false,
      })),
      explanation: 'Unknown: no usable forecast is available.',
    })
    renderWithProviders(<CheckpointPanel />, {
      plan: plan({ routes: [route({ checkpoints: [checkpoint(), missing] })] }),
    })
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Mile 25.0, unknown risk' }))
    const detail = screen.getByRole('article')
    expect(within(detail).getByText('No forecast available: not assessed')).toBeInTheDocument()
    expect(within(detail).getAllByText('Unknown').length).toBeGreaterThan(0)
    expect(within(detail).queryByText('Low')).not.toBeInTheDocument()
  })
})
