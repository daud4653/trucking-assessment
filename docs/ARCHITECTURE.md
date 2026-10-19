# Architecture

## Overview

A modular monolith: a single Django service serves a versioned JSON API and the built React app
from one origin. There are no background workers. Planning runs synchronously within bounded
provider timeouts (typically 3–15 s), and the 48-hour corridor forecast is fetched as a separate
request so route results appear first.

```
Browser (React)                         Django
─────────────────                       ──────────────────────────────────────────────
PlanForm ── POST /route-plans ────────▶ api.views ─▶ use_cases.create_plan
                                                       │  reserve idempotency row (Postgres)
                                                       ▼
                                                     RoutePlanner (application)
                                                       ├─ GeocodingProvider ─▶ Photon
                                                       ├─ RoutingProvider  ─▶ Valhalla (truck)
                                                       ├─ domain.checkpointing / timing
                                                       ├─ WeatherProvider  ─▶ Open-Meteo (batched)
                                                       ├─ domain.risk       (per checkpoint)
                                                       ├─ domain.aggregation(per route)
                                                       └─ domain.recommendation (ranking)
                                                     presenters.present_plan ─▶ stored JSON
Map + Timeline ─ GET /corridor-forecast ▶ use_cases.get_corridor
                                            domain.corridor (grid) ─▶ WeatherProvider (49 h)
```

## Backend layers

| Layer | Responsibility | Depends on |
|---|---|---|
| `domain/` | Thresholds, load rules, checkpoint placement, ETA interpolation, distance-weighted aggregation, ranking, corridor grid. Pure functions over frozen dataclasses. | stdlib only |
| `application/` | Use cases (`RoutePlanner`, `CorridorForecaster`, `create_plan`), provider **ports** (`Protocol`s), DTOs, response presenters, idempotency. | domain, ORM model |
| `infrastructure/` | Vendor adapters, pydantic validation of provider payloads, unit conversion at the boundary, HTTP client (timeouts, bounded jittered retries, `Retry-After`), caching decorators. | application ports |
| `api/` | DRF request validation, HTTP status and error envelope, throttles. No business logic. | application |
| `wiring.py` | Composition root: builds adapters from settings. Tests replace these factories with in-memory fakes. | all |

Domain code never sees vendor JSON, Django requests or the database. Domain tests run without a
database or network.

### Provider choices

| Need | Provider | Why | Constraints |
|---|---|---|---|
| Routing | Valhalla (FOSSGIS public server) | `truck` costing accepts vehicle weight; `alternates` returns up to 2 extra routes; per-maneuver `time`/`length`/`begin_shape_index` give segment-level ETAs; keyless. | Fair use; ~1,500 km route limit; no live traffic. |
| Weather | Open-Meteo | Hourly `wind_speed_10m` (mph), `rain`+`showers` (mm), `snowfall` (cm); many locations per request; 16-day horizon; keyless. | Accumulations are per hour, so they are interpreted as hourly mean intensity. |
| Geocoding | Photon (komoot) | OSM-based; permits search-as-you-type, unlike Nominatim. | Fair use. |
| Base map | OpenFreeMap | Keyless vector tiles for MapLibre. | Attribution required (shown). |

Each provider sits behind a protocol in `application/ports.py`. Replacing one means writing a new
adapter and changing `wiring.py`.

### Persistence

`RoutePlan` stores the normalized request, the presented result, a request fingerprint, and an
optional `(idempotency_scope, idempotency_key)` pair with a partial unique constraint. Plans
expire after `PLAN_RETENTION_HOURS` (default 24):

- expired plans return 404;
- `purge_expired_plans` deletes them;
- plans are anonymous, and the unguessable UUID is the only handle to one;
- the idempotency scope is a salted hash of the client address, never the address itself.

Transient values (checkpoints, weather series) are not tables. They live in the stored result or in
the cache.

### Caching

Django's cache uses the **database backend**, so rate limits, provider caches and corridor results
are shared by every gunicorn worker without adding Redis.

| Entry | Key includes | TTL |
|---|---|---|
| Geocode | provider, normalized query, limit | 24 h |
| Route set | provider, origin/destination (5 dp), gross weight, route count | 1 h |
| Weather series | provider, point (4 dp), start hour, end hour | 30 min |
| Corridor payload | plan id | 30 min |

Failures are never cached. Cached weather keeps its original `retrieved_at`, so the freshness shown
in the UI is the provider's, not the cache's.

### Reliability and abuse controls

- Explicit connect (5 s) and read (20 s) timeouts. At most 2 retries, only for transport errors and
  429/5xx, with exponential backoff and jitter. A `Retry-After` longer than 5 s fails fast instead
  of tying up a worker.
- Weather failures are isolated per batch of 50 locations: affected checkpoints become `unavailable`
  and the plan still returns, marked uncertain. A routing or geocoding failure fails the request
  with `503 provider_unavailable`.
- Throttles (DRF, shared cache): planning 20/h, corridor 60/h, geocode 60/min, reads 240/h per
  client. `429` responses include `Retry-After`.
- Idempotency: see the docstring in `application/use_cases.py`. Concurrent duplicates are resolved
  by the unique constraint and tested with threads against Postgres.
- Request bodies are capped at 16 KB and accepted only as JSON. Provider base URLs come only from
  settings, so user input never becomes a fetch target.

## Frontend

```
app/            router (/, /plans/:planId), QueryClient provider
features/
  route-planning/        PlanForm (react-hook-form + zod), LocationField (ARIA combobox),
                         API functions, zod response schemas, PlannerPage
  route-comparison/      PlanSelectionProvider, RouteComparison, RiskStrip, RouteLayers (map)
  checkpoint-inspection/ CheckpointPanel, CheckpointDetail, CheckpointList
  weather-forecast/      CorridorViewProvider, CorridorLayer (map), ForecastTimeline, legend, inspector
components/map/          MapView (one MapLibre instance), useGeoJsonSource / useLayer / useLayerClick
lib/                     api-client (typed errors), formatting, risk labels/colors
```

- **Server state** lives in TanStack Query. The created plan is written into the cache and the URL
  changes to `/plans/:id`, so the page reloads and links share. Starting a new submission aborts
  the previous request, so an older response can never replace a newer one.
- **Contract.** Every response is parsed with a zod schema that mirrors
  `application/presenters.py`. A mismatch surfaces as `invalid_response` instead of rendering bad
  data.
- **UI state.** Selection (route, checkpoint) and heatmap controls (offset, metric, visibility) live
  in two small feature contexts. Both are keyed by plan id and derived during render, so changing
  plans resets selection without remounting the map. Page status is a discriminated union
  (`empty | loading | error | ready`).
- **Map.** The map is created once. Each feature component adds its own source and layers on mount
  and pushes updates with `setData`. Draw order is fixed by invisible anchor layers, so the heatmap
  stays under the routes and the routes under the checkpoints.
- **Heatmap smoothness.** Cell polygons are uploaded once. A slider step runs `setFeatureState` on
  at most 320 cells: no network request, no worker re-tiling, no React re-render of the map.
- **No business rules in the client.** Risk levels, metric levels, band labels and the ranking all
  come from the API. The client only formats them and draws segments.

## Design decisions worth knowing

- **Ranking tiers.** A route with a No Travel checkpoint, or with less than 95% forecast coverage,
  is ranked behind fully assessed routes regardless of mileage. Otherwise a 2-mile No Travel
  segment could outrank 20 Severe miles, or missing data could look like a clean route.
- **Distance attribution.** Each checkpoint represents the stretch between the midpoints to its
  neighbours, so the represented miles add up exactly to the route length. A 10-mile sampling and
  a 50-mile sampling of the same weather produce the same mileage totals.
- **Decimal at the boundary.** Converting 2.54 mm in floating point gives 0.0999… in, which would
  fall below the 0.10 in/hr threshold. Conversions use `Decimal`, and explanation text truncates
  rather than rounds.
