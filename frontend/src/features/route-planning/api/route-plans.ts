import { apiRequest } from '@/lib/api-client'
import {
  geocodeResponseSchema,
  type GeocodeResult,
  type RoutePlan,
  type RoutePlanRequest,
  routePlanSchema,
} from './schemas'

const BASE = '/api/v1'

export function createRoutePlan(
  request: RoutePlanRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<RoutePlan> {
  return apiRequest(`${BASE}/route-plans/`, {
    method: 'POST',
    body: request,
    headers: { 'Idempotency-Key': idempotencyKey },
    schema: routePlanSchema,
    signal,
  })
}

export function fetchRoutePlan(planId: string, signal?: AbortSignal): Promise<RoutePlan> {
  return apiRequest(`${BASE}/route-plans/${encodeURIComponent(planId)}/`, {
    schema: routePlanSchema,
    signal,
  })
}

export async function searchLocations(
  query: string,
  signal?: AbortSignal,
): Promise<GeocodeResult[]> {
  const params = new URLSearchParams({ q: query })
  const response = await apiRequest(`${BASE}/geocode/?${params.toString()}`, {
    schema: geocodeResponseSchema,
    signal,
  })
  return response.results
}
