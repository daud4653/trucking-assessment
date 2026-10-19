import { createContext, type ReactNode, use, useState } from 'react'
import type { Checkpoint, Route, RoutePlan } from '@/features/route-planning/api/schemas'

interface PlanSelection {
  plan: RoutePlan
  selectedRoute: Route
  selectedCheckpoint: Checkpoint | null
  selectRoute: (routeId: string) => void
  selectCheckpoint: (checkpointId: string | null) => void
}

interface SelectionState {
  planId: string | null
  routeId: string | null
  checkpointId: string | null
}

const PlanSelectionContext = createContext<PlanSelection | null>(null)

/**
 * Selected route and checkpoint for the current plan. Selection belongs to
 * a plan id: when the plan changes, it falls back to the new plan's
 * recommended route without remounting the map below this provider.
 */
export function PlanSelectionProvider({
  plan,
  children,
}: {
  plan: RoutePlan | null
  children: ReactNode
}) {
  const [state, setState] = useState<SelectionState>({
    planId: null,
    routeId: null,
    checkpointId: null,
  })
  const value = plan ? buildSelection(plan, state, setState) : null
  return <PlanSelectionContext value={value}>{children}</PlanSelectionContext>
}

export function usePlanSelection(): PlanSelection {
  const value = use(PlanSelectionContext)
  if (value === null) throw new Error('usePlanSelection requires a loaded plan')
  return value
}

function buildSelection(
  plan: RoutePlan,
  state: SelectionState,
  setState: (state: SelectionState) => void,
): PlanSelection {
  const current = state.planId === plan.id
  const selectedRoute = findRoute(plan, current ? state.routeId : null)
  const checkpointId = current ? state.checkpointId : null
  const selectedCheckpoint =
    selectedRoute.checkpoints.find((checkpoint) => checkpoint.id === checkpointId) ?? null
  return {
    plan,
    selectedRoute,
    selectedCheckpoint,
    selectRoute: (routeId) => setState({ planId: plan.id, routeId, checkpointId: null }),
    selectCheckpoint: (id) =>
      setState({ planId: plan.id, routeId: selectedRoute.id, checkpointId: id }),
  }
}

function findRoute(plan: RoutePlan, routeId: string | null): Route {
  const route =
    plan.routes.find((candidate) => candidate.id === routeId) ??
    plan.routes.find((candidate) => candidate.id === plan.recommended_route_id) ??
    plan.routes[0]
  if (route === undefined) throw new Error('Plan has no routes')
  return route
}
