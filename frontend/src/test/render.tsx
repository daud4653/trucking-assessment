import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { PlanSelectionProvider } from '@/features/route-comparison/selection'
import type { RoutePlan } from '@/features/route-planning/api/schemas'

export function renderWithProviders(ui: ReactElement, { plan }: { plan?: RoutePlan } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PlanSelectionProvider plan={plan ?? null}>{children}</PlanSelectionProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
  return { queryClient, ...render(ui, { wrapper }) }
}
