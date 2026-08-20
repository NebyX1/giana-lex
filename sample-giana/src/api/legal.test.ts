import { beforeEach, expect, test, vi } from 'vitest'
import { fixtureDraft } from '../test/workspaceFixture'
import { clearCsrfToken } from './client'
import { legalApi, streamCaseEvents } from './legal'

beforeEach(() => clearCsrfToken())

function sse(sequence: number) {
  return `id: ${sequence}\nevent: case.updated\ndata: ${JSON.stringify({ id: `e${sequence}`, case_id: 'case-1', sequence_number: sequence, event_type: 'case.updated', payload: {}, occurred_at: '2026-08-17T00:00:00Z' })}\n\n`
}

test('reconecta con Last-Event-ID y deduplica eventos repetidos', async () => {
  const controller = new AbortController()
  const received: number[] = []
  let call = 0
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
    call += 1
    if (call === 2) expect(new Headers(init?.headers).get('Last-Event-ID')).toBe('1')
    return new Response(call === 1 ? sse(1) : sse(1) + sse(2), { headers: { 'Content-Type': 'text/event-stream' } })
  })
  await streamCaseEvents('case-1', { signal: controller.signal, reconnectDelay: 0, onEvent: (event) => { received.push(event.sequence_number); if (event.sequence_number === 2) controller.abort() } })
  expect(received).toEqual([1, 2])
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

test('envía approve y reject con versión e idempotencia explícitas', async () => {
  const requests: Array<{ key: string | null; body: Record<string, unknown> }> = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://test').pathname
    if (path === '/api/auth/csrf') return Response.json({ csrf_token: 'csrf' })
    if (path.endsWith('/review')) {
      requests.push({ key: new Headers(init?.headers).get('Idempotency-Key'), body: JSON.parse(String(init?.body)) })
      return Response.json({ command_id: 'review-1', status: 'completed' }, { status: 202 })
    }
    throw new Error(`Unexpected request ${path}`)
  })

  await legalApi.review('case-1', true, [], fixtureDraft, 'same-review-key')
  await legalApi.review('case-1', false, [{ severity: 'high', category: 'human_review', description: 'Corregir competencia.', suggested_action: 'Corregir.', blocks_output: true }], fixtureDraft, 'same-review-key')

  expect(requests.map((request) => request.key)).toEqual(['same-review-key', 'same-review-key'])
  expect(requests[0].body).toEqual({ approved: true, findings: [], draft_id: 'draft-2', draft_version: 2 })
  expect(requests[1].body).toMatchObject({ approved: false, draft_id: 'draft-2', draft_version: 2 })
})

test('propaga el conflicto 409 de versión obsoleta', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = new URL(String(input), 'http://test').pathname
    if (path === '/api/auth/csrf') return Response.json({ csrf_token: 'csrf' })
    return Response.json({ error: 'draft_version_mismatch', message: 'El borrador fue actualizado.' }, { status: 409 })
  })
  await expect(legalApi.review('case-1', true, [], fixtureDraft, 'stale-key')).rejects.toMatchObject({ status: 409, code: 'draft_version_mismatch' })
})
