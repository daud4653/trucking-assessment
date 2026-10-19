import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/lib/api-client'
import { defaultDeparture, toLocalInputValue } from '@/lib/date-time'
import { renderWithProviders } from '@/test/render'
import type { RoutePlanRequest } from '../api/schemas'
import type { PlanFormValues } from '../schemas/plan-form'
import { PlanForm } from './PlanForm'

function values(overrides: Partial<PlanFormValues> = {}): PlanFormValues {
  return {
    origin: { query: 'Chicago, IL', lat: 41.88, lon: -87.63 },
    destination: { query: 'Peoria, IL' },
    departure: toLocalInputValue(defaultDeparture()),
    loadWeight: 42_000,
    interval: '25',
    ...overrides,
  }
}

function setup(
  overrides: Partial<PlanFormValues> = {},
  onSubmit = vi.fn<(request: RoutePlanRequest) => Promise<unknown>>().mockResolvedValue(undefined),
) {
  renderWithProviders(
    <PlanForm defaultValues={values(overrides)} isPending={false} onSubmit={onSubmit} onCancel={vi.fn()} />,
  )
  return { onSubmit, user: userEvent.setup() }
}

describe('PlanForm', () => {
  it('submits a typed request with an explicit UTC departure', async () => {
    const { onSubmit, user } = setup()
    await user.click(screen.getByRole('radio', { name: '50 mi' }))
    await user.click(screen.getByRole('button', { name: 'Compare routes' }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const request = onSubmit.mock.calls[0]?.[0]
    if (!request) throw new Error('not submitted')
    expect(request).toMatchObject({
      origin: { query: 'Chicago, IL', lat: 41.88, lon: -87.63 },
      destination: { query: 'Peoria, IL' },
      load_weight_lb: 42_000,
      sampling_interval_miles: 50,
    })
    expect(request.destination).not.toHaveProperty('lat')
    expect(request.departure_time).toMatch(/Z$/)
  })

  it('rejects invalid input before calling the API', async () => {
    const { onSubmit, user } = setup({ origin: { query: '' }, loadWeight: 0 })
    await user.click(screen.getByRole('button', { name: 'Compare routes' }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Enter at least 2 characters.')).toBeInTheDocument()
    expect(screen.getByText('Load weight must be at least 1 lb.')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Origin' })).toHaveAttribute('aria-invalid', 'true')
  })

  it('rejects departures more than 7 days ahead', async () => {
    const far = new Date(Date.now() + 9 * 24 * 3_600_000)
    const { onSubmit, user } = setup({ departure: toLocalInputValue(far) })
    await user.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Departure must be within the next 7 days.')).toBeInTheDocument()
  })

  it('rejects identical origin and destination', async () => {
    const { onSubmit, user } = setup({ destination: { query: 'chicago, il', lat: 41.88, lon: -87.63 } })
    await user.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByText('Destination must differ from origin.')).toBeInTheDocument()
  })

  it('maps server field errors onto the matching inputs', async () => {
    const onSubmit = vi.fn().mockRejectedValue(
      new ApiError(422, 'location_not_found', "No location matched 'Peoria, IL'.", {
        destination: ["No location matched 'Peoria, IL'."],
      }),
    )
    const { user } = setup({}, onSubmit)
    await user.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(await screen.findAllByText("No location matched 'Peoria, IL'.")).not.toHaveLength(0)
    expect(screen.getByRole('combobox', { name: 'Destination' })).toHaveAttribute('aria-invalid', 'true')
  })

  it('shows provider outages as a form-level message', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValue(new ApiError(503, 'provider_unavailable', 'The valhalla service is unavailable right now.'))
    const { user } = setup({}, onSubmit)
    await user.click(screen.getByRole('button', { name: 'Compare routes' }))
    expect(await screen.findByText('The valhalla service is unavailable right now.')).toBeInTheDocument()
  })

  it('shows a cancel action and progress text while planning', () => {
    renderWithProviders(
      <PlanForm defaultValues={values()} isPending onSubmit={vi.fn()} onCancel={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Planning routes…' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Requesting truck routes')
  })
})
