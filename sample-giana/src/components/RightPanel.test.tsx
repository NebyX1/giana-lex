import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { fixtureDraft, makeWorkspace } from '../test/workspaceFixture'
import { useCaseWorkspace } from '../features/workflow/useCaseWorkspace'
import { RightPanel } from './RightPanel'

function Harness() {
  const controller = useCaseWorkspace('case-1')
  return <RightPanel mode="durable" sources={[]} sessionId={10} controller={controller} />
}

function reviewWorkspace() {
  const base = makeWorkspace()
  return makeWorkspace({
    case: { ...base.case, state: 'ready_for_human_review' },
    snapshot: { ...base.snapshot, state: 'ready_for_human_review' },
    activity: { kind: 'waiting_human_review', task_type: 'review_draft', task_id: 'task-1', draft_version: 2 },
    draft: fixtureDraft,
    human_tasks: [{ id: 'task-1', case_id: 'case-1', task_type: 'review_draft', status: 'open', payload_json: { draft_version_id: 'draft-2' }, created_at: '2026-08-17T12:00:00Z' }],
    capabilities: { ...base.capabilities, can_view_draft: true, can_review: true, can_reject: true, can_export_docx: true, can_request_second_opinion: true },
  })
}

test('muestra el borrador persistido y exporta DOCX sin reconstruirlo', async () => {
  const requests: Array<{ path: string; body?: string }> = []
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://test').pathname
    requests.push({ path, body: typeof init?.body === 'string' ? init.body : undefined })
    if (path === '/api/auth/csrf') return Response.json({ csrf_token: 'csrf' })
    if (path.endsWith('/workspace')) return Response.json(reviewWorkspace())
    if (path.endsWith('/events/stream')) return new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))
    if (path.endsWith('/generate-docx')) return Response.json({ filename: 'draft.docx', download_url: '/download.docx' }, { status: 201 })
    if (path === '/download.docx') return new Response(new Blob(['docx']))
    throw new Error(`Unexpected ${path}`)
  })

  render(<Harness />)
  expect(await screen.findByText('BORRADOR - Proyecto de resolución')).toBeVisible()
  expect(screen.queryByLabelText('Capacidades del expediente')).not.toBeInTheDocument()
  expect(screen.queryByText('can export docx')).not.toBeInTheDocument()
  expect(screen.getByText('Artículo 33 del TOCAF.')).toBeVisible()
  expect(screen.getAllByText('evidence-3')).toHaveLength(2)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Exportar DOCX' }))
  await waitFor(() => expect(requests.find((request) => request.path.endsWith('/generate-docx'))?.body).toBe('{}'))
})

test('envía identidad y versión del draft al aprobar y muestra conflictos 409', async () => {
  let reviewBody: Record<string, unknown> | undefined
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = new URL(String(input), 'http://test').pathname
    if (path === '/api/auth/csrf') return Response.json({ csrf_token: 'csrf' })
    if (path.endsWith('/workspace')) return Response.json(reviewWorkspace())
    if (path.endsWith('/events/stream')) return new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))
    if (path.endsWith('/review')) {
      reviewBody = JSON.parse(String(init?.body))
      return Response.json({ message: 'La versión ya fue revisada.', error: 'workflow_conflict' }, { status: 409 })
    }
    throw new Error(`Unexpected ${path}`)
  })

  render(<Harness />)
  await userEvent.setup().click(await screen.findByRole('button', { name: 'Aprobar borrador' }))
  await screen.findByText(/El borrador fue actualizado/)
  expect(reviewBody).toEqual({ approved: true, findings: [], draft_id: 'draft-2', draft_version: 2 })
})
