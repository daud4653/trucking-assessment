import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { searchLocations } from '../api/route-plans'

const MIN_QUERY_LENGTH = 3
const DEBOUNCE_MS = 300

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export function useLocationSuggestions(query: string, enabled: boolean) {
  const normalized = query.trim()
  const debounced = useDebouncedValue(normalized, DEBOUNCE_MS)
  const active = enabled && debounced.length >= MIN_QUERY_LENGTH
  return useQuery({
    queryKey: ['geocode', debounced.toLowerCase()],
    queryFn: ({ signal }) => searchLocations(debounced, signal),
    enabled: active,
    staleTime: 24 * 60 * 60_000,
    placeholderData: keepPreviousData,
    retry: false,
  })
}
