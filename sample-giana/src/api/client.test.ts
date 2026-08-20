import { afterEach, expect, test, vi } from 'vitest'

import { ApiError, apiRequest } from './client'

afterEach(() => {
  vi.restoreAllMocks()
})

test('conserva diagnóstico sin contaminar el mensaje visible', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => new Response(JSON.stringify({
      error: 'internal_error',
      message: 'Ocurrio un error interno.',
      request_id: 'request-123',
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'request-123' },
    }))

  await expect(apiRequest('/api/failure')).rejects.toMatchObject({
    status: 500,
    code: 'internal_error',
    requestId: 'request-123',
    message: 'Ocurrio un error interno.',
  })
  try {
    await apiRequest('/api/failure')
  } catch (error) {
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).diagnosticMessage()).toBe('Ocurrio un error interno. (error: internal_error | HTTP 500 | ref: request-123)')
  }
})
