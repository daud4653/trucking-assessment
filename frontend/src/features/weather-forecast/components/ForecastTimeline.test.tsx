import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { formatDateTime } from '@/lib/date-time'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { corridor } from '@/test/fixtures'
import type { HeatmapMetric } from '../heatmap'
import { type CorridorState, ForecastTimeline } from './ForecastTimeline'

function Harness({ state }: { state: CorridorState }) {
  const [offset, setOffset] = useState(0)
  const [metric, setMetric] = useState<HeatmapMetric>('risk')
  const [visible, setVisible] = useState(true)
  return (
    <ForecastTimeline
      corridor={state}
      offset={offset}
      onOffsetChange={setOffset}
      metric={metric}
      onMetricChange={setMetric}
      visible={visible}
      onVisibleChange={setVisible}
      tripWindow={{ start: 0, end: 5, label: 'Shaded: Route A on the road until 19:00' }}
    />
  )
}

describe('ForecastTimeline', () => {
  it('slider covers 0-48 hours and shows the valid forecast time', () => {
    render(<Harness state={{ status: 'ready', forecast: corridor() }} />)
    const slider = screen.getByRole('slider')
    expect(slider).toHaveAttribute('min', '0')
    expect(slider).toHaveAttribute('max', '48')

    fireEvent.change(slider, { target: { value: '24' } })
    expect(screen.getByText('+24 h')).toBeInTheDocument()
    const validTime = formatDateTime('2026-10-21T14:00:00.000Z')
    expect(document.querySelector('output')).toHaveTextContent(validTime)
    expect(slider).toHaveAttribute('aria-valuetext', `24 hours after departure, ${validTime}`)
  })

  it('disables the slider while loading and offers retry on error', async () => {
    const retry = vi.fn()
    const { rerender } = render(<Harness state={{ status: 'loading' }} />)
    expect(screen.getByRole('slider')).toBeDisabled()
    expect(screen.getByText('Loading 48-hour corridor forecast…')).toBeInTheDocument()

    rerender(<Harness state={{ status: 'error', message: 'Corridor forecast unavailable.', retry }} />)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry' }))
    expect(retry).toHaveBeenCalled()
  })

  it('reports coverage and freshness when ready', () => {
    render(<Harness state={{ status: 'ready', forecast: corridor() }} />)
    expect(screen.getByText(/Coverage 50%/)).toBeInTheDocument()
    expect(screen.getByText(/retrieved/)).toBeInTheDocument()
  })
})
