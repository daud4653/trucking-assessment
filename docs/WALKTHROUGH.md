# Walkthrough outline (5–10 min)

Before recording: start the backend and frontend, and clear the cache
(`manage.py shell -c "from django.core.cache import cache; cache.clear()"`) so loading states
show. Pick a trip with three alternatives, for example Minneapolis → Duluth.

1. **Problem and scope (0:30).** Compare routes by forecast weather risk, load and time. Say what
   it is not: a legal truck-routing engine.
2. **Plan a trip (1:00).** Type in the origin to show suggestions in the combobox. Set departure,
   load and interval. Submit, and point out the honest progress text and Cancel. The URL changes
   to `/plans/:id`, so the plan can be shared.
3. **Route comparison (1:30).** Ranks, Recommended label, mileage per level in the strip, coverage.
   Read one ranking explanation and show it names the deciding criterion. Mention the fewer-routes
   notice if it appears.
4. **Map (1:00).** Grey alternatives; the selected route colored by checkpoint risk. Click an
   alternative to select it, then a checkpoint marker.
5. **Checkpoint inspection (1:00).** ETA, wind valid hour and precipitation hour, measurements with
   bands, decisive metric, load rule. Explain unknown versus Low.
6. **Corridor heatmap (1:30).** Move the slider 0 → 48 h and point out that there are no network
   requests (open the DevTools Network tab). Switch Risk/Wind/Rain/Snow. Legend bands come from the
   backend. Click a cell to inspect it. The shaded band is the selected route's time on the road;
   explain heatmap time versus checkpoint ETA.
7. **Risk engine and tests (1:30).** Open `domain/risk.py` (band table with explicit inclusivity,
   strict load comparisons) and `domain/recommendation.py` (tiers, then lexicographic key). Run
   `pytest`. Show the 30,000/40,000 lb boundary tests and the Decimal conversion test (2.54 mm =
   0.10 in).
8. **Architecture and ops (1:00).** Layers, provider ports, idempotency and rate limits, caching.
   Show the methodology dialog.
9. **Limitations (0:30).** Public provider limits (≈930 mi), weight-only truck profile, hourly mean
   precipitation.
