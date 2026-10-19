import { useNavigate, useParams } from 'react-router'
import { WorkspaceLayout } from '@/components/layout/WorkspaceLayout'
import { MapView } from '@/components/map/MapView'
import { CheckpointPanel } from '@/features/checkpoint-inspection/components/CheckpointPanel'
import { PlanOverview } from '@/features/route-comparison/components/PlanOverview'
import { RouteComparison } from '@/features/route-comparison/components/RouteComparison'
import { RouteLayers } from '@/features/route-comparison/map/RouteLayers'
import { PlanSelectionProvider } from '@/features/route-comparison/selection'
import {
  WeatherCorridorLayer,
  WeatherCorridorOverlays,
} from '@/features/weather-forecast/components/WeatherCorridor'
import { CorridorViewProvider } from '@/features/weather-forecast/corridor-view'
import { defaultDeparture, toLocalInputValue } from '@/lib/date-time'
import type { RoutePlan } from '../api/schemas'
import { MapStatus } from '../components/MapStatus'
import { PlanForm } from '../components/PlanForm'
import { TripEditor } from '../components/TripEditor'
import { useCreateRoutePlan, useRoutePlan } from '../hooks/useRoutePlan'
import { toPlanView } from '../plan-view'
import { formValuesFromPlan, type PlanFormValues } from '../schemas/plan-form'

export function PlannerPage() {
  const { planId } = useParams()
  const navigate = useNavigate()
  const planQuery = useRoutePlan(planId)
  const creator = useCreateRoutePlan((plan) => void navigate(`/plans/${plan.id}`))
  const view = toPlanView(planId, planQuery.data, planQuery.error, () => void planQuery.refetch())
  const plan = view.status === 'ready' ? view.plan : null
  const form = (
    <PlanForm
      key={plan?.id ?? 'new'}
      defaultValues={initialFormValues(plan)}
      isPending={creator.isPending}
      onSubmit={creator.submit}
      onCancel={creator.cancel}
    />
  )

  return (
    <PlanSelectionProvider plan={plan}>
      <CorridorViewProvider planId={plan?.id ?? null}>
        <WorkspaceLayout
          title={plan ? `${plan.origin.label} → ${plan.destination.label}` : 'New plan'}
          sidebar={
            plan ? (
              <>
                <PlanOverview />
                <RouteComparison />
                <TripEditor>{form}</TripEditor>
              </>
            ) : (
              form
            )
          }
          map={
            <MapView
              label="Route map"
              overlay={plan ? <WeatherCorridorOverlays /> : <MapStatus view={view} planning={creator.isPending} />}
            >
              {plan && (
                <>
                  <WeatherCorridorLayer />
                  <RouteLayers />
                </>
              )}
            </MapView>
          }
          details={plan ? <CheckpointPanel /> : null}
        />
      </CorridorViewProvider>
    </PlanSelectionProvider>
  )
}

function initialFormValues(plan: RoutePlan | null): PlanFormValues {
  if (plan) return formValuesFromPlan(plan, toLocalInputValue(new Date(plan.departure_time)))
  return {
    origin: { query: '' },
    destination: { query: '' },
    departure: toLocalInputValue(defaultDeparture()),
    loadWeight: 40_000,
    interval: '25',
  }
}
