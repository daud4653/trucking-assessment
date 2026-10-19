import type { ZodType } from 'zod'
import { z } from 'zod'

const errorBodySchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.unknown()).optional(),
  }),
})

export type FieldErrors = Record<string, string[]>

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown> | undefined

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  get retryAfterSeconds(): number | undefined {
    const value = this.details?.retry_after_seconds
    return typeof value === 'number' ? value : undefined
  }

  fieldErrors(): FieldErrors {
    const result: FieldErrors = {}
    for (const [field, value] of Object.entries(this.details ?? {})) {
      result[field] = flattenMessages(value)
    }
    return result
  }
}

interface RequestOptions<T> {
  schema: ZodType<T>
  method?: 'GET' | 'POST'
  body?: unknown
  headers?: Record<string, string>
  signal?: AbortSignal | undefined
}

export async function apiRequest<T>(path: string, options: RequestOptions<T>): Promise<T> {
  const init: RequestInit = {
    method: options.method ?? 'GET',
    headers: {
      Accept: 'application/json',
      ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    signal: options.signal ?? null,
  }
  if (options.body !== undefined) init.body = JSON.stringify(options.body)

  let response: Response
  try {
    response = await fetch(path, init)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Could not reach the server. Check your connection.')
  }

  const payload: unknown = await response.json().catch(() => undefined)
  if (!response.ok) throw toApiError(response.status, payload)

  const parsed = options.schema.safeParse(payload)
  if (!parsed.success) {
    throw new ApiError(
      response.status,
      'invalid_response',
      'The server returned data in an unexpected format.',
    )
  }
  return parsed.data
}

function toApiError(status: number, payload: unknown): ApiError {
  const parsed = errorBodySchema.safeParse(payload)
  if (parsed.success) {
    const { code, message, details } = parsed.data.error
    return new ApiError(status, code, message, details)
  }
  return new ApiError(status, 'http_error', `Request failed (HTTP ${status}).`)
}

function flattenMessages(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(flattenMessages)
  if (value && typeof value === 'object') return Object.values(value).flatMap(flattenMessages)
  return []
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
