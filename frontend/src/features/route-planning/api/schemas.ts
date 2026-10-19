import { z } from 'zod'

// Mirrors backend/apps/route_planning/application/presenters.py. Responses are
// parsed with these schemas so a contract drift fails loudly at the boundary.

export const riskLevelSchema = z.enum(['low', 'moderate', 'high', 'severe', 'no_travel'])
export type RiskLevel = z.infer<typeof riskLevelSchema>

const metricSchema = z.enum(['wind', 'rain', 'snow'])
export type WeatherMetric = z.infer<typeof metricSchema>

const locationSchema = z.object({
  query: z.string(),
  label: z.string(),
  lat: z.number(),
  lon: z.number(),
})

const metricAssessmentSchema = z.object({
  metric: metricSchema,
  value: z.number().nullable(),
  unit: z.string(),
  level: riskLevelSchema.nullable(),
  band: z.string().nullable(),
  invalid: z.boolean(),
})
export type MetricAssessment = z.infer<typeof metricAssessmentSchema>

const checkpointSchema = z.object({
  id: z.string(),
  sequence: z.number().int(),
  distance_miles: z.number(),
  represents_from_miles: z.number(),
  represents_to_miles: z.number(),
  lat: z.number(),
  lon: z.number(),
  eta: z.string(),
  risk_level: riskLevelSchema.nullable(),
  data_status: z.enum(['complete', 'partial', 'unavailable']),
  explanation: z.string(),
  decisive_metrics: z.array(metricSchema),
  metrics: z.array(metricAssessmentSchema),
  load_adjustment: z
    .object({
      rule: z.string(),
      description: z.string(),
      from_level: riskLevelSchema,
      to_level: riskLevelSchema,
    })
    .nullable(),
  weather: z
    .object({
      valid_time: z.string(),
      precipitation_window_end: z.string(),
      retrieved_at: z.string(),
      wind_mph: z.number().nullable(),
      gust_mph: z.number().nullable(),
      rain_in_per_hr: z.number().nullable(),
      snow_in_per_hr: z.number().nullable(),
    })
    .nullable(),
})
export type Checkpoint = z.infer<typeof checkpointSchema>

const milesByLevelSchema = z.object({
  low: z.number(),
  moderate: z.number(),
  high: z.number(),
  severe: z.number(),
  no_travel: z.number(),
})

const routeSchema = z.object({
  id: z.string(),
  label: z.string(),
  rank: z.number().int(),
  screening: z.enum(['assessed', 'uncertain', 'no_travel']),
  is_recommended: z.boolean(),
  ranking_explanation: z.string(),
  distance_miles: z.number(),
  duration_seconds: z.number().int(),
  arrival_time: z.string(),
  eta_method: z.enum(['provider_segments', 'proportional']),
  geometry: z.object({
    type: z.literal('LineString'),
    coordinates: z.array(z.tuple([z.number(), z.number()])),
  }),
  summary: z.object({
    total_miles: z.number(),
    miles_by_level: milesByLevelSchema,
    severe_or_worse_miles: z.number(),
    high_miles: z.number(),
    unknown_miles: z.number(),
    partial_miles: z.number(),
    coverage_ratio: z.number(),
    average_risk: z.number().nullable(),
    peak_level: riskLevelSchema.nullable(),
    is_uncertain: z.boolean(),
    has_no_travel: z.boolean(),
  }),
  checkpoints: z.array(checkpointSchema),
})
export type Route = z.infer<typeof routeSchema>
export type Screening = Route['screening']

const providerSchema = z.object({
  name: z.string(),
  attribution: z.string(),
  profile: z.string().nullable().optional(),
})

export const routePlanSchema = z.object({
  id: z.string().uuid(),
  created_at: z.string(),
  expires_at: z.string(),
  origin: locationSchema,
  destination: locationSchema,
  departure_time: z.string(),
  load_weight_lb: z.number().int(),
  sampling_interval_miles: z.union([z.literal(10), z.literal(25), z.literal(50)]),
  recommended_route_id: z.string(),
  routes: z.array(routeSchema).min(1),
  notices: z.array(
    z.object({
      code: z.string(),
      message: z.string(),
      severity: z.enum(['info', 'warning', 'critical']),
    }),
  ),
  providers: z.object({
    routing: providerSchema,
    weather: providerSchema,
    geocoding: providerSchema,
  }),
  methodology: z.object({
    min_coverage_ratio: z.number(),
    precipitation: z.string(),
    wind: z.string(),
  }),
})
export type RoutePlan = z.infer<typeof routePlanSchema>
export type Notice = RoutePlan['notices'][number]

const levelIndexArray = z.array(z.number().int().min(0).max(4).nullable())
const valueArray = z.array(z.number().nullable())

export const corridorForecastSchema = z.object({
  plan_id: z.string(),
  base_time: z.string(),
  cell_size_degrees: z.number(),
  cells: z.array(z.tuple([z.number(), z.number(), z.number(), z.number()])),
  frames: z.array(
    z.object({
      offset_hours: z.number().int(),
      valid_time: z.string(),
      risk: levelIndexArray,
      wind_level: levelIndexArray,
      rain_level: levelIndexArray,
      snow_level: levelIndexArray,
      wind_mph: valueArray,
      rain_in_per_hr: valueArray,
      snow_in_per_hr: valueArray,
    }),
  ),
  scales: z.record(metricSchema, z.array(z.object({ level: riskLevelSchema, band: z.string() }))),
  retrieved_at: z.string().nullable(),
  coverage_ratio: z.number(),
  attribution: z.string(),
})
export type CorridorForecast = z.infer<typeof corridorForecastSchema>
export type CorridorFrame = CorridorForecast['frames'][number]

export const geocodeResponseSchema = z.object({
  results: z.array(z.object({ label: z.string(), lat: z.number(), lon: z.number() })),
  attribution: z.string(),
})
export type GeocodeResult = z.infer<typeof geocodeResponseSchema>['results'][number]

export interface RoutePlanRequest {
  origin: { query: string; lat?: number; lon?: number }
  destination: { query: string; lat?: number; lon?: number }
  departure_time: string
  load_weight_lb: number
  sampling_interval_miles: 10 | 25 | 50
}
