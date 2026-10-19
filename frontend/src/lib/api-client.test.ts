import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'
import { ApiError, apiRequest } from './api-client'

const schema = z.object({ ok: z.boolean() })

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiRequest', () => {
  it('returns schema-validated data', async () => {
    mockFetch(200, { ok: true })
    await expect(apiRequest('/x', { schema })).resolves.toEqual({ ok: true })
  })

  it('parses the backend error envelope', async () => {
    mockFetch(429, {
      error: { code: 'rate_limited', message: 'Too many requests.', details: { retry_after_seconds: 120 } },
    })
    const error = await apiRequest('/x', { schema }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 429, code: 'rate_limited' })
    expect((error as ApiError).retryAfterSeconds).toBe(120)
  })

  it('flattens nested field errors', async () => {
    mockFetch(400, {
      error: {
        code: 'validation_error',
        message: 'Some fields are invalid.',
        details: { origin: { query: ['Too long.'] }, load_weight_lb: ['Too heavy.'] },
      },
    })
    const error = (await apiRequest('/x', { schema }).catch((e: unknown) => e)) as ApiError
    expect(error.fieldErrors()).toEqual({ origin: ['Too long.'], load_weight_lb: ['Too heavy.'] })
  })

  it('rejects responses that do not match the contract', async () => {
    mockFetch(200, { ok: 'yes' })
    await expect(apiRequest('/x', { schema })).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it('reports network failures distinctly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(apiRequest('/x', { schema })).rejects.toMatchObject({ code: 'network_error' })
  })
})
