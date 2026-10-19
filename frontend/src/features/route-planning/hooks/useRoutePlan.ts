import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef } from 'react'
import { createRoutePlan, fetchRoutePlan } from '../api/route-plans'
import type { RoutePlan, RoutePlanRequest } from '../api/schemas'

export const routePlanKey = (planId: string) => ['route-plan', planId] as const

export function useRoutePlan(planId: string | undefined) {
  return useQuery({
    queryKey: routePlanKey(planId ?? ''),
    queryFn: ({ signal }) => fetchRoutePlan(planId ?? '', signal),
    enabled: planId !== undefined,
    staleTime: Infinity,
  })
}

/**
 * Creates plans. Starting a new submission aborts the previous in-flight
 * request so a slow, older plan can never replace a newer one. Each
 * submission gets a fresh Idempotency-Key.
 */
export function useCreateRoutePlan(onCreated: (plan: RoutePlan) => void) {
  const queryClient = useQueryClient()
  const controllerRef = useRef<AbortController | null>(null)

  const mutation = useMutation({
    mutationFn: (request: RoutePlanRequest) => {
      controllerRef.current?.abort()
      const controller = new AbortController()
      controllerRef.current = controller
      return createRoutePlan(request, crypto.randomUUID(), controller.signal)
    },
    onSuccess: (plan) => {
      queryClient.setQueryData(routePlanKey(plan.id), plan)
      onCreated(plan)
    },
  })

  const cancel = () => {
    controllerRef.current?.abort()
    controllerRef.current = null
    mutation.reset()
  }

  return { submit: mutation.mutateAsync, cancel, isPending: mutation.isPending }
}
