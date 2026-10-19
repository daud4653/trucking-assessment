import { apiRequest } from '@/lib/api-client'
import {
  type CorridorForecast,
  corridorForecastSchema,
} from '@/features/route-planning/api/schemas'

export function fetchCorridorForecast(
  planId: string,
  signal?: AbortSignal,
): Promise<CorridorForecast> {
  return apiRequest(`/api/v1/route-plans/${encodeURIComponent(planId)}/corridor-forecast/`, {
    schema: corridorForecastSchema,
    signal,
  })
}
