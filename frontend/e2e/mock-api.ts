import type { Page, Route as PlaywrightRoute } from '@playwright/test'

/**
 * Deterministic API responses covering every risk state, so end-to-end tests
 * never depend on live providers or today's weather.
 */
export const PLAN_ID = '0b8a7f8e-1c2d-4e5f-8a9b-0c1d2e3f4a5b'
const DEPARTURE = new Date(Date.now() + 2 * 3_600_000)
DEPARTURE.setUTCMinutes(0, 0, 0)

type Level = 'low' | 'moderate' | 'high' | 'severe' | 'no_travel' | null

const BANDS = {
  wind: ['below 25 mph', '25 to below 35 mph', '35 to below 45 mph', '45 to below 55 mph', '55 mph or above'],
  rain: ['below 0.10 in/hr', '0.10 to below 0.25 in/hr', '0.25 to below 0.50 in/hr', '0.50 to 1.00 in/hr inclusive', 'above 1.00 in/hr'],
  snow: ['below 0.50 in/hr', '0.50 to below 1.00 in/hr', '1.00 to below 2.00 in/hr', '2.00 to 3.00 in/hr inclusive', 'above 3.00 in/hr'],
}
const LEVELS = ['low', 'moderate', 'high', 'severe', 'no_travel'] as const
const WIND_FOR: Record<string, number> = { low: 10, moderate: 28, high: 38, severe: 48, no_travel: 58 }

function iso(date: Date) {
  return date.toISOString().replace('.000Z', 'Z')
}

function checkpoints(routeId: string, levels: Level[], miles: number, lonOffset: number) {
  const step = miles / (levels.length - 1)
  return levels.map((level, i) => {
    const distance = i * step
    const eta = new Date(DEPARTURE.getTime() + (distance / 55) * 3_600_000)
    const wind = level ? WIND_FOR[level] ?? 10 : null
    const metricLevel = level ? LEVELS.indexOf(level) : -1
    return {
      id: `${routeId}-cp-${i}`,
      sequence: i,
      distance_miles: distance,
      represents_from_miles: i === 0 ? 0 : distance - step / 2,
      represents_to_miles: i === levels.length - 1 ? miles : distance + step / 2,
      lat: 41.88 - (i / (levels.length - 1)) * 3.2,
      lon: -87.63 - (i / (levels.length - 1)) * 2.5 + (i > 0 && i < levels.length - 1 ? lonOffset : 0),
      eta: iso(eta),
      risk_level: level,
      data_status: level ? 'complete' : 'unavailable',
      explanation: level
        ? `${level === 'no_travel' ? 'No Travel' : level.charAt(0).toUpperCase() + level.slice(1)}: wind is ${wind} mph (${BANDS.wind[metricLevel]}).`
        : 'Unknown: no usable forecast is available for the estimated arrival time, so this checkpoint is not assessed.',
      decisive_metrics: level ? ['wind'] : [],
      metrics: [
        { metric: 'wind', value: wind, unit: 'mph', level, band: level ? BANDS.wind[metricLevel] : null, invalid: false },
        { metric: 'rain', value: level ? 0 : null, unit: 'in/hr', level: level ? 'low' : null, band: level ? BANDS.rain[0] : null, invalid: false },
        { metric: 'snow', value: level ? 0 : null, unit: 'in/hr', level: level ? 'low' : null, band: level ? BANDS.snow[0] : null, invalid: false },
      ],
      load_adjustment: null,
      weather: level
        ? {
            valid_time: iso(eta),
            precipitation_window_end: iso(eta),
            retrieved_at: iso(new Date()),
            wind_mph: wind,
            gust_mph: wind ? wind + 8 : null,
            rain_in_per_hr: 0,
            snow_in_per_hr: 0,
          }
        : null,
    }
  })
}

function route(id: string, label: string, rank: number, levels: Level[], extra: Record<string, unknown>) {
  const miles = 300
  const cps = checkpoints(id, levels, miles, (rank - 2) * 0.4)
  return {
    id,
    label,
    rank,
    distance_miles: miles,
    arrival_time: cps.at(-1)?.eta,
    eta_method: 'provider_segments',
    geometry: { type: 'LineString', coordinates: cps.map((c) => [c.lon, c.lat]) },
    checkpoints: cps,
    ...extra,
  }
}

function summary(levels: Level[], overrides: Record<string, unknown> = {}) {
  const per = 300 / (levels.length - 1)
  const miles = { low: 0, moderate: 0, high: 0, severe: 0, no_travel: 0 }
  let unknown = 0
  levels.forEach((level, i) => {
    const share = i === 0 || i === levels.length - 1 ? per / 2 : per
    if (level) miles[level] += share
    else unknown += share
  })
  return {
    total_miles: 300,
    miles_by_level: miles,
    severe_or_worse_miles: miles.severe + miles.no_travel,
    high_miles: miles.high,
    unknown_miles: unknown,
    partial_miles: 0,
    coverage_ratio: (300 - unknown) / 300,
    average_risk: 0.5,
    peak_level: 'severe',
    is_uncertain: unknown / 300 > 0.05,
    has_no_travel: miles.no_travel > 0,
    ...overrides,
  }
}

const A: Level[] = ['low', 'low', 'moderate', 'high', 'low', 'low', 'low']
const B: Level[] = ['low', 'moderate', 'severe', 'severe', 'high', 'low', 'low']
const C: Level[] = ['low', 'low', 'no_travel', 'low', null, null, 'low']

export const plan = {
  id: PLAN_ID,
  created_at: iso(new Date()),
  expires_at: iso(new Date(Date.now() + 86_400_000)),
  origin: { query: 'Chicago', label: 'Chicago, Illinois, United States', lat: 41.88, lon: -87.63 },
  destination: { query: 'Peoria', label: 'Peoria, Illinois, United States', lat: 38.68, lon: -90.13 },
  departure_time: iso(DEPARTURE),
  load_weight_lb: 45000,
  sampling_interval_miles: 50,
  recommended_route_id: 'route-1',
  routes: [
    route('route-1', 'Route A', 1, A, {
      screening: 'assessed', is_recommended: true, duration_seconds: 19_800,
      ranking_explanation: 'Ranked first: fewer severe-or-worse miles than Route B (0.00 vs 100.00).',
      summary: summary(A, { peak_level: 'high', average_risk: 0.58 }),
    }),
    route('route-2', 'Route B', 2, B, {
      screening: 'assessed', is_recommended: false, duration_seconds: 18_000,
      ranking_explanation: 'Ranked second: more severe-or-worse miles than Route A (100.00 vs 0.00).',
      summary: summary(B, { peak_level: 'severe', average_risk: 1.33 }),
    }),
    route('route-3', 'Route C', 3, C, {
      screening: 'no_travel', is_recommended: false, duration_seconds: 17_000,
      ranking_explanation: 'Ranked third: this route contains a No Travel segment, whereas Route B is fully assessed with no No Travel segment.',
      summary: summary(C, { peak_level: 'no_travel', average_risk: 1.0 }),
    }),
  ],
  notices: [
    { code: 'routing_scope', message: 'Routes use the provider truck profile. Confirm legality before dispatch.', severity: 'info' },
    { code: 'incomplete_weather', message: '2 checkpoints lack complete forecast data.', severity: 'warning' },
  ],
  providers: {
    routing: { name: 'valhalla', profile: 'truck', attribution: 'Valhalla' },
    weather: { name: 'open-meteo', attribution: 'Open-Meteo' },
    geocoding: { name: 'photon', attribution: 'Photon' },
  },
  methodology: { min_coverage_ratio: 0.95, precipitation: 'p', wind: 'w' },
}

function corridor() {
  const cells: [number, number, number, number][] = []
  for (let row = 0; row < 18; row++) {
    for (let col = 0; col < 16; col++) {
      const south = 38.4 + row * 0.2
      const west = -90.6 + col * 0.2
      cells.push([west, south, west + 0.2, south + 0.2])
    }
  }
  const frames = Array.from({ length: 49 }, (_, offset) => {
    const risk = cells.map((_, i) => {
      if ((i + offset) % 37 === 0) return null
      const band = Math.floor(((i % 16) + offset / 3) % 10)
      return Math.min(4, Math.max(0, band - 5))
    })
    return {
      offset_hours: offset,
      valid_time: iso(new Date(DEPARTURE.getTime() + offset * 3_600_000)),
      risk,
      wind_level: risk,
      rain_level: risk.map((r) => (r === null ? null : 0)),
      snow_level: risk.map((r) => (r === null ? null : 0)),
      wind_mph: risk.map((r) => (r === null ? null : [10, 28, 38, 48, 58][r] ?? 10)),
      rain_in_per_hr: risk.map((r) => (r === null ? null : 0)),
      snow_in_per_hr: risk.map((r) => (r === null ? null : 0)),
    }
  })
  return {
    plan_id: PLAN_ID,
    base_time: iso(DEPARTURE),
    cell_size_degrees: 0.2,
    cells,
    frames,
    scales: Object.fromEntries(
      Object.entries(BANDS).map(([metric, bands]) => [
        metric,
        bands.map((band, i) => ({ level: LEVELS[i], band })),
      ]),
    ),
    retrieved_at: iso(new Date()),
    coverage_ratio: 0.97,
    attribution: 'Open-Meteo',
  }
}

export interface MockOptions {
  planDelayMs?: number
  planError?: { status: number; body: unknown }
}

export async function mockApi(page: Page, options: MockOptions = {}) {
  const json = (r: PlaywrightRoute, status: number, body: unknown) =>
    r.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

  await page.route('**/api/v1/geocode/**', (r) => {
    const q = new URL(r.request().url()).searchParams.get('q') ?? ''
    const place = q.toLowerCase().startsWith('chi')
      ? { label: 'Chicago, Illinois, United States', lat: 41.88, lon: -87.63 }
      : { label: 'Peoria, Illinois, United States', lat: 38.68, lon: -90.13 }
    return json(r, 200, { results: [place], attribution: 'Photon' })
  })
  await page.route('**/api/v1/route-plans/', async (r) => {
    if (options.planDelayMs) await new Promise((resolve) => setTimeout(resolve, options.planDelayMs))
    if (options.planError) return json(r, options.planError.status, options.planError.body)
    return json(r, 201, plan)
  })
  await page.route(`**/api/v1/route-plans/${PLAN_ID}/`, (r) => json(r, 200, plan))
  await page.route(`**/api/v1/route-plans/${PLAN_ID}/corridor-forecast/`, (r) => json(r, 200, corridor()))
}
