# Risk model and ranking

Source: `backend/apps/route_planning/domain/`. Every boundary below has a test in
`tests/domain/test_risk.py`.

## Metric thresholds

`[a, b)` includes a and excludes b; `[a, b]` includes both; `(a, ∞)` excludes a.

| Level | Wind (mph) | Rain (in/hr) | Snow (in/hr) |
|---|---|---|---|
| Low | [0, 25) | [0, 0.10) | [0, 0.5) |
| Moderate | [25, 35) | [0.10, 0.25) | [0.5, 1.0) |
| High | [35, 45) | [0.25, 0.50) | [1.0, 2.0) |
| Severe | [45, 55) | [0.50, 1.00] | [2.0, 3.0] |
| No Travel | [55, ∞) | (1.00, ∞) | (3.0, ∞) |

The assessment's table writes "25–34" for wind. That is read as "25 to below 35", so 34.9 mph is
Moderate, consistent with the "35–44 High" row and the brief's explicit "≥55" No Travel.

## Load rules (wind only)

| Rule | Condition | Result |
|---|---|---|
| any load | wind ≥ 55 mph | No Travel (already the wind table's result) |
| `heavy_load_severe_wind` | 45 ≤ wind < 55 **and** load **>** 30,000 lb | No Travel |
| `heavy_load_high_wind` | 35 ≤ wind < 45 **and** load **>** 40,000 lb | Severe |

The comparisons are strict: exactly 30,000 lb or 40,000 lb does **not** trigger a rule. Load rules
never change rain or snow levels. *Load* means cargo weight. The router receives cargo plus a
configurable tare (`TRUCK_TARE_WEIGHT_LB`, default 35,000 lb) as gross weight.

## Checkpoint classification

1. Classify each available metric with its scale.
2. Apply the first matching load rule to wind, if it raises the level.
3. The checkpoint level is the **highest** of wind (load-adjusted), rain and snow.
4. *Decisive metrics* are those at that highest level. The explanation names their measurement and
   band, and the load rule when one applied. It is generated from the result, for example:
   `Severe: wind is 42 mph and the load is 45,000 lb, triggering the heavy-load wind adjustment (35 to below 45 mph wind with load over 40,000 lb).`

Data quality:

| Situation | `data_status` | Level |
|---|---|---|
| All three metrics present | `complete` | as classified |
| Some metrics missing or invalid | `partial` | from available metrics. This is a **minimum**, and the explanation says so. |
| No forecast for the ETA, or provider failure | `unavailable` | `null` (Unknown), **never Low** |

Negative, NaN or infinite provider values count as invalid (treated as missing and flagged). A
negative or non-integer load raises an error.

## Units and forecast-hour selection (Open-Meteo)

| Metric | Provider field | Conversion |
|---|---|---|
| Wind | `wind_speed_10m`, requested in mph | none. Sustained 10 m wind; gusts are shown but not classified. |
| Rain | `rain + showers`, mm over the preceding hour | ÷ 25.4 → in/hr (Decimal) |
| Snow | `snowfall`, cm over the preceding hour | ÷ 2.54 → in/hr (Decimal) |

The provider stamps an hour's accumulation at the **end** of that hour, so the value at T covers
(T−1h, T]. That accumulation divided by one hour is the mean intensity for the hour. It is compared
with the in/hr thresholds; bursts within the hour can be heavier.

For an ETA *t*:

- **wind**: the sample nearest *t* (instantaneous quantity);
- **rain and snow**: the sample at ceil(*t*), the hour whose window contains *t*.

Both valid times are returned and shown with each checkpoint.

## Route aggregation (distance-weighted)

Each checkpoint represents the road from the midpoint with its previous checkpoint to the midpoint
with its next one (the origin and destination take the half-segments at the ends). These stretches
tile the route exactly.

- **miles by level**: sum of represented miles per level;
- **unknown miles**: represented miles with no assessment;
- **coverage**: miles backed by *complete* forecasts ÷ total miles;
- **average risk**: Σ(miles × score) ÷ Σ(known miles), where Low = 0, Moderate = 1, High = 2,
  Severe = 3, No Travel = 4. It is `null` when nothing is known;
- **uncertain**: coverage < 95%.

Miles are rounded to 0.01 (half-even) and the average to 0.001 *before* ranking, so ranking
compares exactly the values the API reports.

## Ranking

The policy is lexicographic, with screening tiers first:

| Order | Key | Better |
|---|---|---|
| 1 | tier: assessed → uncertain → contains No Travel | lower |
| 2 | Severe + No Travel miles | fewer |
| 3 | High miles | fewer |
| 4 | average risk (unknown average sorts last) | lower |
| 5 | drive time (s) | shorter |
| 6 | provider route order | stable tie-break |

**Best-ranked** is not the same as **safe**:

- a route with any No Travel checkpoint is labelled as such and never called recommended;
- when every route has one, a critical notice says none meets the thresholds;
- an uncertain best-ranked route is labelled "Best ranked · uncertain".

Each route's explanation names the first criterion that separates it from its neighbour in the
ranking.

## Corridor heatmap

The heatmap is separate from route risk. Route risk uses each checkpoint's own ETA; the heatmap
shows the whole corridor at one moment, departure + offset (0–48 h), snapped to the nearest
forecast hour. Each cell is classified with the same scales and load rules. The `risk` layer is
the combined, load-adjusted level; the wind, rain and snow layers show raw metric levels. Cells are
drawn flat with no interpolation, and missing samples are drawn as "No forecast".
