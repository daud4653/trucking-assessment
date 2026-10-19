import type {
  Checkpoint,
  CorridorForecast,
  Route,
  RoutePlan,
} from '@/features/route-planning/api/schemas'

export function checkpoint(overrides: Partial<Checkpoint> = {}): Checkpoint {
  return {
    id: 'route-1-cp-0',
    sequence: 0,
    distance_miles: 0,
    represents_from_miles: 0,
    represents_to_miles: 12.5,
    lat: 41.88,
    lon: -87.63,
    eta: '2026-10-20T14:00:00Z',
    risk_level: 'low',
    data_status: 'complete',
    explanation: 'Low: wind 8 mph, rain 0.00 in/hr and snow 0.00 in/hr are below every Moderate threshold.',
    decisive_metrics: ['wind', 'rain', 'snow'],
    metrics: [
      { metric: 'wind', value: 8, unit: 'mph', level: 'low', band: 'below 25 mph', invalid: false },
      { metric: 'rain', value: 0, unit: 'in/hr', level: 'low', band: 'below 0.10 in/hr', invalid: false },
      { metric: 'snow', value: 0, unit: 'in/hr', level: 'low', band: 'below 0.50 in/hr', invalid: false },
    ],
    load_adjustment: null,
    weather: {
      valid_time: '2026-10-20T14:00:00Z',
      precipitation_window_end: '2026-10-20T14:00:00Z',
      retrieved_at: '2026-10-20T13:50:00Z',
      wind_mph: 8,
      gust_mph: 12,
      rain_in_per_hr: 0,
      snow_in_per_hr: 0,
    },
    ...overrides,
  }
}

export function route(overrides: Partial<Route> = {}): Route {
  const id = overrides.id ?? 'route-1'
  return {
    id,
    label: 'Route A',
    rank: 1,
    screening: 'assessed',
    is_recommended: true,
    ranking_explanation: 'Ranked first: fewer severe-or-worse miles than Route B (0.00 vs 20.00).',
    distance_miles: 25,
    duration_seconds: 1800,
    arrival_time: '2026-10-20T14:30:00Z',
    eta_method: 'provider_segments',
    geometry: {
      type: 'LineString',
      coordinates: [
        [-87.63, 41.88],
        [-87.7, 41.7],
      ],
    },
    summary: {
      total_miles: 25,
      miles_by_level: { low: 25, moderate: 0, high: 0, severe: 0, no_travel: 0 },
      severe_or_worse_miles: 0,
      high_miles: 0,
      unknown_miles: 0,
      partial_miles: 0,
      coverage_ratio: 1,
      average_risk: 0,
      peak_level: 'low',
      is_uncertain: false,
      has_no_travel: false,
    },
    checkpoints: [
      checkpoint({ id: `${id}-cp-0` }),
      checkpoint({
        id: `${id}-cp-1`,
        sequence: 1,
        distance_miles: 25,
        represents_from_miles: 12.5,
        represents_to_miles: 25,
        eta: '2026-10-20T14:30:00Z',
      }),
    ],
    ...overrides,
  }
}

export function plan(overrides: Partial<RoutePlan> = {}): RoutePlan {
  return {
    id: '4f3c2b1a-0000-4000-8000-000000000001',
    created_at: '2026-10-20T13:00:00Z',
    expires_at: '2026-10-21T13:00:00Z',
    origin: { query: 'Chicago', label: 'Chicago, Illinois', lat: 41.88, lon: -87.63 },
    destination: { query: 'Joliet', label: 'Joliet, Illinois', lat: 41.52, lon: -88.08 },
    departure_time: '2026-10-20T14:00:00Z',
    load_weight_lb: 42000,
    sampling_interval_miles: 25,
    recommended_route_id: 'route-1',
    routes: [route()],
    notices: [],
    providers: {
      routing: { name: 'valhalla', profile: 'truck', attribution: 'Valhalla' },
      weather: { name: 'open-meteo', attribution: 'Open-Meteo' },
      geocoding: { name: 'photon', attribution: 'Photon' },
    },
    methodology: { min_coverage_ratio: 0.95, precipitation: 'p', wind: 'w' },
    ...overrides,
  }
}

export function corridor(overrides: Partial<CorridorForecast> = {}): CorridorForecast {
  const frames = Array.from({ length: 49 }, (_, offset) => ({
    offset_hours: offset,
    valid_time: new Date(Date.parse('2026-10-20T14:00:00Z') + offset * 3_600_000).toISOString(),
    risk: [offset >= 24 ? 3 : 0, null],
    wind_level: [offset >= 24 ? 3 : 0, null],
    rain_level: [0, null],
    snow_level: [0, null],
    wind_mph: [offset >= 24 ? 48 : 8, null],
    rain_in_per_hr: [0, null],
    snow_in_per_hr: [0, null],
  }))
  return {
    plan_id: '4f3c2b1a-0000-4000-8000-000000000001',
    base_time: '2026-10-20T14:00:00Z',
    cell_size_degrees: 0.2,
    cells: [
      [-87.8, 41.6, -87.6, 41.8],
      [-87.6, 41.6, -87.4, 41.8],
    ],
    frames,
    scales: {
      wind: [
        { level: 'low', band: 'below 25 mph' },
        { level: 'moderate', band: '25 to below 35 mph' },
        { level: 'high', band: '35 to below 45 mph' },
        { level: 'severe', band: '45 to below 55 mph' },
        { level: 'no_travel', band: '55 mph or above' },
      ],
      rain: [],
      snow: [],
    },
    retrieved_at: '2026-10-20T13:55:00Z',
    coverage_ratio: 0.5,
    attribution: 'Open-Meteo',
    ...overrides,
  }
}
