import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { makeWorkspace } from '../../test/workspaceFixture'
import { useCaseWorkspace } from './useCaseWorkspace'

test('ignora hidrataciones del caso anterior y comparte refresh single-flight', async () => {
  let resolveFirst: ((response: Response) => void) | undefined
  let caseTwoRequests = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = String(input)
    if (url.includes('/case-1/workspace')) return new Promise<Response>((resolve) => { resolveFirst = resolve })
    if (url.includes('/case-2/workspace')) {
      caseTwoRequests += 1
      const base = makeWorkspace()
      return Promise.resolve(Response.json(makeWorkspace({ case: { ...base.case, id: 'case-2', title: 'Caso dos' }, snapshot: { ...base.snapshot, case_id: 'case-2', title: 'Caso dos' } })))
    }
    if (url.includes('/events/stream')) return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })
    throw new Error(`Unexpected request ${url}`)
  })

  const hook = renderHook(({ caseId }) => useCaseWorkspace(caseId), { initialProps: { caseId: 'case-1' } })
  hook.rerender({ caseId: 'case-2' })
  await waitFor(() => expect(hook.result.current.legalCase?.title).toBe('Caso dos'))
  await act(async () => { resolveFirst?.(Response.json(makeWorkspace({ case: { ...makeWorkspace().case, title: 'Caso uno tardío' } }))) })
  expect(hook.result.current.legalCase?.title).toBe('Caso dos')

  const before = caseTwoRequests
  await act(async () => { await Promise.all([hook.result.current.refresh(), hook.result.current.refresh()]) })
  expect(caseTwoRequests).toBe(before + 1)
})
