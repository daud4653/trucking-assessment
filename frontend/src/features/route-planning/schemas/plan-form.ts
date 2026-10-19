import { z } from 'zod'
import { fromLocalInputValue } from '@/lib/date-time'
import type { RoutePlan, RoutePlanRequest } from '../api/schemas'

export const MAX_LOAD_WEIGHT_LB = 80_000
export const SAMPLING_INTERVALS = ['10', '25', '50'] as const
const MAX_PAST_MS = 60 * 60_000
const MAX_AHEAD_MS = 7 * 24 * 60 * 60_000

const locationSchema = z.object({
  query: z
    .string()
    .trim()
    .min(2, 'Enter at least 2 characters.')
    .max(200, 'Keep this under 200 characters.'),
  lat: z.number().optional(),
  lon: z.number().optional(),
})
export type LocationValue = z.infer<typeof locationSchema>

export const planFormSchema = z
  .object({
    origin: locationSchema,
    destination: locationSchema,
    departure: z.string().superRefine((value, ctx) => {
      const date = fromLocalInputValue(value)
      if (date === null) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Enter a valid date and time.' })
        return
      }
      const delta = date.getTime() - Date.now()
      if (delta < -MAX_PAST_MS) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Departure cannot be more than 1 hour ago.',
        })
      } else if (delta > MAX_AHEAD_MS) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Departure must be within the next 7 days.',
        })
      }
    }),
    loadWeight: z
      .number({ invalid_type_error: 'Enter the load weight in pounds.' })
      .int('Use whole pounds.')
      .min(1, 'Load weight must be at least 1 lb.')
      .max(MAX_LOAD_WEIGHT_LB, `Maximum supported load is ${MAX_LOAD_WEIGHT_LB.toLocaleString()} lb.`),
    interval: z.enum(SAMPLING_INTERVALS),
  })
  .superRefine((values, ctx) => {
    const sameText =
      values.origin.query.trim().toLowerCase() === values.destination.query.trim().toLowerCase()
    const sameCoordinates =
      values.origin.lat === values.destination.lat && values.origin.lon === values.destination.lon
    if (sameText && sameCoordinates) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['destination', 'query'],
        message: 'Destination must differ from origin.',
      })
    }
  })

export type PlanFormValues = z.infer<typeof planFormSchema>

export function toPlanRequest(values: PlanFormValues): RoutePlanRequest {
  const departure = fromLocalInputValue(values.departure)
  if (departure === null) throw new Error('Departure was not validated.')
  return {
    origin: toLocation(values.origin),
    destination: toLocation(values.destination),
    departure_time: departure.toISOString(),
    load_weight_lb: values.loadWeight,
    sampling_interval_miles: Number(values.interval) as RoutePlanRequest['sampling_interval_miles'],
  }
}

function toLocation(value: LocationValue): RoutePlanRequest['origin'] {
  const query = value.query.trim()
  if (value.lat === undefined || value.lon === undefined) return { query }
  return { query, lat: value.lat, lon: value.lon }
}

export function formValuesFromPlan(plan: RoutePlan, departureInput: string): PlanFormValues {
  return {
    origin: { query: plan.origin.label, lat: plan.origin.lat, lon: plan.origin.lon },
    destination: {
      query: plan.destination.label,
      lat: plan.destination.lat,
      lon: plan.destination.lon,
    },
    departure: departureInput,
    loadWeight: plan.load_weight_lb,
    interval: String(plan.sampling_interval_miles) as PlanFormValues['interval'],
  }
}

/** Maps API field names onto form field paths for server-side errors. */
export const SERVER_FIELD_PATHS: Record<string, keyof PlanFormValues | `${'origin' | 'destination'}.query`> = {
  origin: 'origin.query',
  destination: 'destination.query',
  departure_time: 'departure',
  load_weight_lb: 'loadWeight',
  sampling_interval_miles: 'interval',
}
