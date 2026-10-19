import { useQuery } from '@tanstack/react-query'
import { fetchCorridorForecast } from '../api/corridor'

export function useCorridorForecast(planId: string) {
  return useQuery({
    queryKey: ['corridor-forecast', planId],
    queryFn: ({ signal }) => fetchCorridorForecast(planId, signal),
    staleTime: 15 * 60_000,
  })
}
