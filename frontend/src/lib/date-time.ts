const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short',
})

const timeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

export function browserTimeZone(): string {
  return timeZone
}

export function formatDateTime(iso: string): string {
  return dateTimeFormat.format(new Date(iso))
}

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${String(minutes).padStart(2, '0')}m`
}

export function formatAge(iso: string, now: Date = new Date()): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 60_000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  return `${hours} h ago`
}

/** Value for <input type="datetime-local"> in the browser's zone. */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** Interprets a datetime-local value in the browser's zone; null if invalid. */
export function fromLocalInputValue(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function defaultDeparture(now: Date = new Date()): Date {
  const next = new Date(now.getTime() + 60 * 60_000)
  next.setMinutes(Math.ceil(next.getMinutes() / 15) * 15, 0, 0)
  return next
}
