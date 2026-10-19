import { createContext, type ReactNode, use, useState } from 'react'
import type { HeatmapMetric } from './heatmap'

interface CorridorView {
  offset: number
  metric: HeatmapMetric
  visible: boolean
  inspectedCell: number | null
  setOffset: (offset: number) => void
  setMetric: (metric: HeatmapMetric) => void
  setVisible: (visible: boolean) => void
  inspectCell: (cell: number | null) => void
}

interface ViewState {
  planId: string | null
  offset: number
  inspectedCell: number | null
}

const CorridorViewContext = createContext<CorridorView | null>(null)

/**
 * Heatmap controls shared by the map layer and its overlays. Offset and the
 * inspected cell reset per plan; metric and visibility are user preferences
 * that persist across plans.
 */
export function CorridorViewProvider({
  planId,
  children,
}: {
  planId: string | null
  children: ReactNode
}) {
  const [state, setState] = useState<ViewState>({ planId, offset: 0, inspectedCell: null })
  const [metric, setMetric] = useState<HeatmapMetric>('risk')
  const [visible, setVisible] = useState(true)
  const current = state.planId === planId

  const value: CorridorView = {
    offset: current ? state.offset : 0,
    inspectedCell: current ? state.inspectedCell : null,
    metric,
    visible,
    setOffset: (offset) =>
      setState((prev) => ({
        planId,
        offset,
        inspectedCell: prev.planId === planId ? prev.inspectedCell : null,
      })),
    inspectCell: (cell) =>
      setState((prev) => ({
        planId,
        offset: prev.planId === planId ? prev.offset : 0,
        inspectedCell: cell,
      })),
    setMetric,
    setVisible,
  }
  return <CorridorViewContext value={value}>{children}</CorridorViewContext>
}

export function useCorridorView(): CorridorView {
  const value = use(CorridorViewContext)
  if (value === null) throw new Error('useCorridorView must be used within CorridorViewProvider')
  return value
}
