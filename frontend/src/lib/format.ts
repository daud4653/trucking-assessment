const milesFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 })
const integerFormat = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })

export function formatMiles(value: number): string {
  return `${milesFormat.format(value)} mi`
}

export function formatPounds(value: number): string {
  return `${integerFormat.format(value)} lb`
}

export function formatPercent(ratio: number): string {
  return `${Math.floor(ratio * 1000) / 10}%`
}

export function formatMeasurement(value: number | null, unit: string): string {
  if (value === null) return 'No data'
  const digits = unit === 'mph' ? 1 : 2
  return `${value.toFixed(digits)} ${unit}`
}
