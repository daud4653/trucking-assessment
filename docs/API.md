# API reference (`/api/v1/`)

JSON only. Times are ISO 8601 UTC (`Z`). Distances are in miles, wind in mph, and precipitation in
in/hr. Response field definitions live in `backend/apps/route_planning/application/presenters.py`;
the frontend mirrors them in `frontend/src/features/route-planning/api/schemas.ts`.

## Errors

Every error response uses this envelope:

```json
{ "error": { "code": "validation_error", "message": "Some fields are invalid.", "details": { "load_weight_lb": ["Ensure this value is less than or equal to 80000."] } } }
```

| Status | `code` | When |
|---|---|---|
| 400 | `validation_error`, `invalid_idempotency_key` | Invalid input |
| 404 | `plan_not_found`, `not_found` | Unknown or expired plan; unknown endpoint |
| 409 | `idempotency_in_progress` | Same key is still being processed (`Retry-After: 2`) |
| 415 | `unsupported_media_type` | Body is not JSON |
| 422 | `location_not_found`, `same_location`, `route_not_found`, `route_too_long`, `idempotency_key_reused` | Valid input that cannot be planned |
| 429 | `rate_limited` | Throttled; `Retry-After` header and `details.retry_after_seconds` |
| 502 | `invalid_provider_data` | Provider data failed domain validation |
| 503 | `provider_unavailable` | Routing or geocoding provider failed after retries |

## `POST /route-plans/`

Headers: `Content-Type: application/json`. Optional: `Idempotency-Key: <1–255 chars>`.

```json
{
  "origin": { "query": "Chicago, IL", "lat": 41.8781, "lon": -87.6298 },
  "destination": { "query": "St. Louis, MO" },
  "departure_time": "2026-10-20T08:00:00-05:00",
  "load_weight_lb": 42000,
  "sampling_interval_miles": 25
}
```

- **Locations.** `query` is 1–200 characters. `lat`/`lon` are optional but must come together; when
  present they are used as given, otherwise the query is geocoded.
- **`departure_time`** must include an offset or `Z`. It must be no more than 1 h in the past and
  within the next 7 days.
- **`load_weight_lb`**: integer from 1 to 80,000 (cargo only).
- **`sampling_interval_miles`**: one of 10, 25, 50.

**201 Created**, with header `Location: /api/v1/route-plans/{id}/`. A replay returns
`Idempotent-Replayed: true`. Response shape (abridged):

```jsonc
{
  "id": "uuid", "created_at": "…", "expires_at": "…",
  "origin": { "query", "label", "lat", "lon" }, "destination": { … },
  "departure_time": "…", "load_weight_lb": 42000, "sampling_interval_miles": 25,
  "recommended_route_id": "route-1",
  "routes": [{
    "id": "route-1", "label": "Route A", "rank": 1,
    "screening": "assessed | uncertain | no_travel",
    "is_recommended": true, "ranking_explanation": "Ranked first: …",
    "distance_miles": 296.4, "duration_seconds": 17520, "arrival_time": "…",
    "eta_method": "provider_segments | proportional",
    "geometry": { "type": "LineString", "coordinates": [[lon, lat], …] },   // simplified for display
    "summary": {
      "total_miles", "miles_by_level": { "low", "moderate", "high", "severe", "no_travel" },
      "severe_or_worse_miles", "high_miles", "unknown_miles", "partial_miles",
      "coverage_ratio", "average_risk" /* null if nothing known */, "peak_level",
      "is_uncertain", "has_no_travel"
    },
    "checkpoints": [{
      "id": "route-1-cp-3", "sequence": 3, "distance_miles": 75.0,
      "represents_from_miles": 62.5, "represents_to_miles": 87.5,
      "lat", "lon", "eta",
      "risk_level": "low | moderate | high | severe | no_travel | null",
      "data_status": "complete | partial | unavailable",
      "explanation": "…", "decisive_metrics": ["wind"],
      "metrics": [{ "metric": "wind", "value": 42.0, "unit": "mph", "level": "high", "band": "35 to below 45 mph", "invalid": false }, …],
      "load_adjustment": { "rule", "description", "from_level", "to_level" } | null,
      "weather": { "valid_time", "precipitation_window_end", "retrieved_at", "wind_mph", "gust_mph", "rain_in_per_hr", "snow_in_per_hr" } | null
    }]
  }],
  "notices": [{ "code": "fewer_alternatives | incomplete_weather | all_routes_no_travel | routing_scope", "message", "severity": "info | warning | critical" }],
  "providers": { "routing": { "name", "profile", "attribution" }, "weather": { … }, "geocoding": { … } },
  "methodology": { "min_coverage_ratio": 0.95, "precipitation": "…", "wind": "…" }
}
```

## `GET /route-plans/{id}/`

Returns the same body as the create response. Returns 404 once the plan has expired.

## `GET /route-plans/{id}/corridor-forecast/`

Returns all 49 hourly frames at once, so the slider needs no further requests. Results are cached
for 30 min.

```jsonc
{
  "plan_id": "uuid",
  "base_time": "…",                 // departure rounded to the nearest forecast hour
  "cell_size_degrees": 0.2,
  "cells": [[west, south, east, north], …],
  "frames": [{
    "offset_hours": 0, "valid_time": "…",
    "risk":       [0, 1, null, …],   // combined, load-adjusted level index per cell (0=Low … 4=No Travel)
    "wind_level": […], "rain_level": […], "snow_level": […],
    "wind_mph":   [8.4, …], "rain_in_per_hr": […], "snow_in_per_hr": […]
  }, …],                             // 49 frames: offsets 0–48
  "scales": { "wind": [{ "level": "low", "band": "below 25 mph" }, …], "rain": […], "snow": […] },
  "retrieved_at": "…", "coverage_ratio": 0.98, "attribution": "…"
}
```

## `GET /geocode/?q=<3–200 chars>`

Location suggestions. Throttled at 60/min.

```json
{ "results": [{ "label": "Dallas, Texas, United States", "lat": 32.77, "lon": -96.79 }], "attribution": "…" }
```

## `GET /health/` and `GET /ready/`

- `/health/` is liveness: it always returns `{"status": "ok"}` while the process is serving.
- `/ready/` checks the database and cache and returns 200 or 503 with
  `{"status", "checks": {"database", "cache"}}`. External providers are deliberately not probed.
