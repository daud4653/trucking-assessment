import type { CorridorFrame } from '@/features/route-planning/api/schemas'

export type HeatmapMetric = 'risk' | 'wind' | 'rain' | 'snow'

export const HEATMAP_METRICS: readonly { value: HeatmapMetric; label: string }[] = [
  { value: 'risk', label: 'Risk' },
  { value: 'wind', label: 'Wind' },
  { value: 'rain', label: 'Rain' },
  { value: 'snow', label: 'Snow' },
]

export function levelsFor(frame: CorridorFrame, metric: HeatmapMetric): (number | null)[] {
  switch (metric) {
    case 'risk':
      return frame.risk
    case 'wind':
      return frame.wind_level
    case 'rain':
      return frame.rain_level
    case 'snow':
      return frame.snow_level
  }
}

/** Offset (whole hours from the forecast base) nearest to a timestamp. */
export function offsetOf(baseTime: string, iso: string): number {
  return Math.round((new Date(iso).getTime() - new Date(baseTime).getTime()) / 3_600_000)
}
