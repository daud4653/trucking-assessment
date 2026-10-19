# Weather-Aware Truck Routing

Compare up to three truck routes by forecast weather risk, load weight and travel time.
Enter an origin, destination, departure time and load. The app:

1. requests up to three truck routes,
2. places weather checkpoints every 10, 25 or 50 miles along each route,
3. forecasts each checkpoint at the truck's estimated arrival time,
4. classifies the risk using the wind, rain, snow and load rules,
5. ranks the routes and shows everything on a map with a 0–48 hour corridor heatmap.

React + TypeScript frontend, Django REST backend, PostgreSQL. No API keys are needed: the
default providers are public, keyless services.

> This is a weather screening tool. It is not a legal truck-routing engine. Routes use a truck
> profile with the estimated gross weight, but they are not checked for height, hazmat, permits
> or local restrictions.

- [Architecture](docs/ARCHITECTURE.md): layers, data flow, provider choices
- [Risk model and ranking](docs/RISK_MODEL.md): thresholds, load rules, aggregation, units
- [API reference](docs/API.md)
- [Walkthrough outline](docs/WALKTHROUGH.md): script for the recorded demo

## Features

| Area | What is implemented |
|---|---|
| Routing | Valhalla `truck` costing with gross weight. Up to 3 distinct alternatives; duplicates are removed and any shortfall is disclosed. |
| Checkpoints | Measured along the route geometry at 10/25/50 mi, plus origin and destination. Each one represents the half-way stretch to its neighbours. |
| ETAs | Departure time plus the provider's per-maneuver drive times, interpolated by distance and calculated in UTC (DST-safe). |
| Weather | Open-Meteo hourly forecast, many locations per request, cached. Wind uses the forecast hour nearest the ETA; precipitation uses the forecast hour that contains the ETA. |
| Risk | Pure, deterministic engine with exact boundary semantics and Decimal unit conversion. Each checkpoint gets an explanation generated from the calculation. |
| Ranking | Screening tier (assessed, then uncertain, then No Travel), followed by severe-or-worse miles, high miles, mile-weighted average risk, drive time, and provider order as a stable tie-break. |
| Map | MapLibre. Alternatives in grey; the selected route colored by checkpoint risk; checkpoint markers drawn on the map canvas (no DOM markers). |
| Heatmap | Corridor grid of up to 320 cells × 49 hourly frames, loaded in one request. The slider changes only per-cell feature state: no network calls and no re-tiling. Metrics: combined risk (load-adjusted), wind, rain, snow. |
| States | Explicit loading, empty, error, partial-coverage, uncertain and No Travel states. Missing weather is never shown as Low. |
| Ops | Versioned REST API, error envelope, rate limits, idempotency keys, health/readiness checks, JSON logs, CSP, immutable asset caching. |

## Quick start (local)

Requirements: Python 3.12+, Node 20+, PostgreSQL 14+.

```bash
# Backend
createdb trucking
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py runserver 8000

# Frontend (second terminal)
cd frontend
npm ci
npm run dev            # http://localhost:5173, proxies /api to :8000
```

Every setting has a development default (see [.env.example](.env.example)). To override:
`set -a; source .env; set +a` before starting Django. The default database is
`postgres:///trucking`; set `DATABASE_URL` for anything else.

## Checks

```bash
# Backend
cd backend
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/pytest                      # 156 tests, no network access

# Frontend
cd frontend
npm run typecheck
npm run lint
npm test                              # Vitest + Testing Library
npx playwright install chromium       # once
npm run test:e2e                      # Playwright, mocked API, desktop + mobile
npm run build
```

No test calls a live provider: backend tests use in-memory fakes and `httpx.MockTransport`, and
end-to-end tests intercept `/api/v1/**`.

## Repository layout

```
backend/
  config/                    settings (base/development/production/test), urls, CSP middleware, JSON logging
  apps/route_planning/
    domain/                  pure rules: risk, checkpointing, timing, aggregation, ranking, corridor grid
    application/             use cases, ports (provider protocols), DTOs, response presenters
    infrastructure/          Valhalla, Open-Meteo and Photon adapters, HTTP client with retries, caching
    api/                     DRF serializers, views, URLs, error envelope
    models.py                RoutePlan (persisted results + idempotency)
    wiring.py                composition root
  apps/health/               /health and /ready
frontend/
  src/app/                   router, providers
  src/features/
    route-planning/          form, API client + zod contract, page
    route-comparison/        ranked route list, selection state, route map layers
    checkpoint-inspection/   checkpoint detail and list
    weather-forecast/        corridor heatmap layer, timeline slider, legend, cell inspector
  src/components/            map primitives, layout, form controls, risk label
  src/lib/                   API client, query client, formatting
  e2e/                       Playwright specs and API mocks
docs/                        architecture, risk model, API, walkthrough
```

## Deployment

The `Dockerfile` builds one image: it compiles the React app, then runs Django with gunicorn, and
WhiteNoise serves the SPA and its assets from the same origin (no CORS). `render.yaml` is a Render
Blueprint for that image plus managed PostgreSQL. Any platform that runs a container with
`DATABASE_URL` works.

**Status:** not deployed. The production settings were verified locally: gunicorn with
`config.settings.production`, `manage.py check --deploy`, the built SPA under the CSP, and the
health/readiness checks. The Docker image itself was **not built** here because Docker was not
available. Deploying needs a hosting account.

Release steps (Render runs the first two as `preDeployCommand`):

```bash
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py purge_expired_plans     # schedule hourly (cron) to enforce retention
```

### Production checklist

- [ ] `DJANGO_SECRET_KEY` (40+ random characters) and `DJANGO_ALLOWED_HOSTS` set; startup refuses to run otherwise
- [ ] `DATABASE_URL` for a least-privilege database user
- [ ] TLS terminated at the platform; `SECURE_SSL_REDIRECT` and HSTS enabled (default in production settings)
- [ ] `NUM_PROXIES` matches the number of proxies, so rate limits see real client addresses
- [ ] `PROVIDER_USER_AGENT` identifies you (OSM community services ask for a contact)
- [ ] For real traffic, self-host Valhalla and Photon, or switch providers: the public instances are best-effort and fair-use only
- [ ] `purge_expired_plans` scheduled
- [ ] Health check pointed at `/api/v1/ready/`

## Known limitations

- **Truck legality.** Only gross weight is passed to the router (load + configurable 35,000 lb tare). Height, length, hazmat and permits are not modelled.
- **Route length.** The public Valhalla server rejects routes longer than about 930 miles (1,500 km). The app explains this; a self-hosted Valhalla removes the limit.
- **Alternatives.** Valhalla may return fewer than three distinct routes (common on short trips or sparse networks). The app shows what was returned and says so.
- **Traffic.** ETAs use Valhalla's speed model, not live traffic.
- **Precipitation intensity** is the mean over the forecast hour. Short bursts within the hour can exceed it.
- **Sampling.** Weather is sampled at checkpoints, not continuously; a narrow cell between checkpoints can be missed. Use a 10-mile interval for a denser picture.
- **Corridor resolution.** Cells are 0.2°–1.5° depending on trip length (bounded to 320 cells). This is coarser than the checkpoint sampling.
- **Timezone.** Times display in the browser's timezone, not each checkpoint's local zone.
- **Provider quotas.** Open-Meteo's free tier is about 10,000 calls/day, where multi-location requests count per location. Caching reduces repeat cost.
