import type { RiskLevel, Screening } from '@/features/route-planning/api/schemas'

export const RISK_LEVELS: readonly RiskLevel[] = ['low', 'moderate', 'high', 'severe', 'no_travel']

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: 'Low',
  moderate: 'Moderate',
  high: 'High',
  severe: 'Severe',
  no_travel: 'No Travel',
}

export const SCREENING_LABELS: Record<Screening, string> = {
  assessed: 'Fully assessed',
  uncertain: 'Uncertain: incomplete forecast',
  no_travel: 'Contains No Travel segment',
}

export function riskLabel(level: RiskLevel | null): string {
  return level === null ? 'Unknown' : RISK_LABELS[level]
}

/** CSS custom property holding the color for a level (null = unknown). */
export function riskColorVar(level: RiskLevel | null): string {
  return `var(--risk-${level === null ? 'unknown' : level.replace('_', '-')})`
}

export function riskTintVar(level: RiskLevel | null): string {
  return `var(--risk-${level === null ? 'unknown' : level.replace('_', '-')}-tint)`
}

export function levelFromIndex(index: number | null | undefined): RiskLevel | null {
  if (index === null || index === undefined) return null
  return RISK_LEVELS[index] ?? null
}

/** Resolved hex colors from tokens.css, for canvas rendering (MapLibre). */
export function resolveRiskColors(): Record<RiskLevel | 'unknown', string> {
  const style = getComputedStyle(document.documentElement)
  const read = (name: string, fallback: string) =>
    style.getPropertyValue(name).trim() || fallback
  return {
    low: read('--risk-low', '#4c7a55'),
    moderate: read('--risk-moderate', '#c19a1b'),
    high: read('--risk-high', '#d46a1f'),
    severe: read('--risk-severe', '#b3261e'),
    no_travel: read('--risk-no-travel', '#5e1745'),
    unknown: read('--risk-unknown', '#9aa0a3'),
  }
}
