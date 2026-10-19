import type { Checkpoint, RiskLevel } from '@/features/route-planning/api/schemas'

type Position = [number, number]

export interface RiskSegment {
  checkpointId: string
  level: RiskLevel | null
  coordinates: Position[]
}

const EARTH_RADIUS_MILES = 3958.7613

/**
 * Splits a route line into the stretches each checkpoint represents
 * (represents_from_miles..represents_to_miles), for drawing risk along the
 * route. Display geometry is simplified, so its measured length is scaled to
 * the route's reported distance before cutting. Visualization only: risk
 * values come from the API unchanged.
 */
export function splitRouteByCheckpoints(
  coordinates: Position[],
  totalMiles: number,
  checkpoints: Checkpoint[],
): RiskSegment[] {
  if (coordinates.length < 2 || totalMiles <= 0) return []
  const cumulative = cumulativeMiles(coordinates)
  const measured = cumulative[cumulative.length - 1] ?? 0
  if (measured <= 0) return []
  const scale = totalMiles / measured
  const scaled = cumulative.map((miles) => miles * scale)

  return checkpoints
    .filter((checkpoint) => checkpoint.represents_to_miles > checkpoint.represents_from_miles)
    .map((checkpoint) => ({
      checkpointId: checkpoint.id,
      level: checkpoint.risk_level,
      coordinates: slice(
        coordinates,
        scaled,
        checkpoint.represents_from_miles,
        checkpoint.represents_to_miles,
      ),
    }))
}

function slice(coordinates: Position[], cumulative: number[], from: number, to: number): Position[] {
  const result: Position[] = [pointAt(coordinates, cumulative, from)]
  for (let i = 0; i < coordinates.length; i++) {
    const distance = cumulative[i] ?? 0
    const point = coordinates[i]
    if (point && distance > from && distance < to) result.push(point)
  }
  result.push(pointAt(coordinates, cumulative, to))
  return result
}

function pointAt(coordinates: Position[], cumulative: number[], miles: number): Position {
  const last = coordinates.length - 1
  for (let i = 1; i <= last; i++) {
    const end = cumulative[i] ?? 0
    if (end >= miles) {
      const start = cumulative[i - 1] ?? 0
      const a = coordinates[i - 1]
      const b = coordinates[i]
      if (!a || !b) break
      const t = end > start ? (miles - start) / (end - start) : 0
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    }
  }
  return coordinates[last] ?? [0, 0]
}

export function cumulativeMiles(coordinates: Position[]): number[] {
  const result = [0]
  for (let i = 1; i < coordinates.length; i++) {
    const previous = coordinates[i - 1]
    const current = coordinates[i]
    const step = previous && current ? haversineMiles(previous, current) : 0
    result.push((result[i - 1] ?? 0) + step)
  }
  return result
}

function haversineMiles([lon1, lat1]: Position, [lon2, lat2]: Position): number {
  const toRad = Math.PI / 180
  const dLat = (lat2 - lat1) * toRad
  const dLon = (lon2 - lon1) * toRad
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * toRad) * Math.cos(lat2 * toRad) * Math.sin(dLon / 2) ** 2
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.min(1, Math.sqrt(h)))
}
