import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './api-client'

const NON_RETRYABLE_STATUS = new Set([400, 404, 409, 415, 422, 429])

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (error instanceof ApiError && NON_RETRYABLE_STATUS.has(error.status)) return false
          return failureCount < 2
        },
      },
      mutations: { retry: false },
    },
  })
}
