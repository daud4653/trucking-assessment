import { createBrowserRouter } from 'react-router'
import { PlannerPage } from '@/features/route-planning/pages/PlannerPage'
import { NotFoundPage } from './NotFoundPage'

export const router = createBrowserRouter([
  { path: '/', element: <PlannerPage /> },
  { path: '/plans/:planId', element: <PlannerPage /> },
  { path: '*', element: <NotFoundPage /> },
])
