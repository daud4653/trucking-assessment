import { ApiError } from '@/lib/api-client'
import type { RoutePlan } from './api/schemas'

export type PlanView =
  | { status: 'empty' }
  | { status: 'loading' }
  | { status: 'error'; error: unknown; retry: () => void }
  | { status: 'ready'; plan: RoutePlan }

export function toPlanView(
  planId: string | undefined,
  plan: RoutePlan | undefined,
  error: unknown,
  retry: () => void,
): PlanView {
  if (planId === undefined) return { status: 'empty' }
  if (plan) return { status: 'ready', plan }
  if (error) return { status: 'error', error, retry }
  return { status: 'loading' }
}

export function planErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === 'plan_not_found') {
    return 'This plan has expired or does not exist. Plans are kept for 24 hours.'
  }
  if (error instanceof ApiError) return error.message
  return 'The plan could not be loaded.'
}
