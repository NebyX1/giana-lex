import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { makeWorkspace } from '../../test/workspaceFixture'
import { CaseWorkspace } from './CaseWorkspace'

function renderWorkspace(path = '/cases/case-1') {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/cases/:caseId/*" element={<CaseWorkspace />} /></Routes></MemoryRouter>)
}

test('cancela el workflow durable desde el workspace canónico', async () => {
  const requests: string[] = []
  let cancelled = false
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input); requests.push(`${init?.method ?? 'GET'} ${url}`)
    if (url.endsWith('/api/auth/csrf')) return Response.json({ csrf_token: 'csrf' })
    if (url.includes('/events/stream')) return new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))
    if (url.endsWith('/cancel')) { cancelled = true; return Response.json({ command_id: 'command-1', status: 'completed' }, { status: 202 }) }
    if (url.endsWith('/workspace')) {
      const base = makeWorkspace()
      return Response.json(cancelled ? makeWorkspace({
        case: { ...base.case, state: 'cancelled', active_run_id: null, cancelled_at: base.case.updated_at },
        snapshot: { ...base.snapshot, state: 'cancelled', active_run_id: null },
        activity: { kind: 'idle', message: 'Expediente cancelado' },
        capabilities: { ...base.capabilities, can_cancel: false },
      }) : base)
    }
    throw new Error(`Unexpected request ${url}`)
  })
  renderWorkspace()
  const user = userEvent.setup()
  await screen.findByRole('heading', { name: 'Caso durable' })
  await user.click(screen.getByRole('button', { name: 'Cancelar' }))
  await waitFor(() => expect(requests.some((request) => request.includes('POST') && request.endsWith('/cancel'))).toBe(true))
  await screen.findByText('cancelled', { exact: true })
})

test('renderiza y envía el formulario recibido por workspace', async () => {
  const submitted: Array<Record<string, unknown>> = []
  const base = makeWorkspace()
  const workspace = makeWorkspace({
    case: { ...base.case, state: 'awaiting_facts' },
    snapshot: { ...base.snapshot, state: 'awaiting_facts' },
    activity: { kind: 'waiting_user', task_type: 'intake_form', task_id: 'form-1' },
    form: { id: 'form-1', status: 'open', version: 1, workflow_pack_id: 'resolution.generic', workflow_pack_version: 1, created_at: '2026-08-17T12:00:00Z', updated_at: '2026-08-17T12:00:00Z', answers_json: {}, errors_json: {}, schema_json: { id: 'form-1', version: 1, sections: [{ id: 'intake', title: 'Información requerida', fields: [{ key: 'expediente', label: 'Expediente', field_type: 'text', required: true }] }] } },
  })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/api/auth/csrf')) return Response.json({ csrf_token: 'csrf' })
    if (url.includes('/events/stream')) return new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))
    if (url.endsWith('/commands/submit-form')) { submitted.push(JSON.parse(String(init?.body))); return Response.json({ command_id: 'command-1', status: 'completed' }, { status: 202 }) }
    if (url.endsWith('/workspace')) return Response.json(workspace)
    throw new Error(`Unexpected request ${url}`)
  })
  renderWorkspace('/cases/case-1/intake')
  const user = userEvent.setup()
  await screen.findByRole('heading', { name: 'Datos del expediente' })
  await user.type(screen.getByLabelText(/Expediente/), '2026-123')
  await user.click(screen.getByRole('button', { name: 'Confirmar datos' }))
  await waitFor(() => expect(submitted[0]).toMatchObject({ form_id: 'form-1', answers: { expediente: '2026-123' }, partial: false }))
})

test('restaura un parcial y muestra antecedente resuelto y estado canónico de preguntas', async () => {
  const base = makeWorkspace()
  const workspace = makeWorkspace({
    case: { ...base.case, state: 'awaiting_facts', workflow_pack_id: 'resolution.fund_transposition', workflow_pack_version: 2 },
    snapshot: { ...base.snapshot, state: 'awaiting_facts', workflow_pack_id: 'resolution.fund_transposition', workflow_pack_version: 2 },
    activity: { kind: 'waiting_user', task_type: 'complete_form', task_id: 'task-form' },
    form: {
      id: 'form-v2', status: 'partial', version: 1, workflow_pack_id: 'resolution.fund_transposition', workflow_pack_version: 2,
      created_at: '2026-08-17T12:00:00Z', updated_at: '2026-08-17T12:05:00Z', submitted_at: null,
      answers_json: { unit: 'Hacienda' }, errors_json: {}, schema_json: { title: 'Datos para la trasposición presupuestal', sections: [{ id: 'unit', title: 'Expediente y unidad', fields: [{ key: 'unit', label: 'Unidad solicitante o ejecutora', field_type: 'text', required: true }] }] },
    },
    intake_summary: { act_type: 'resolution', subtype: 'fund_transposition', act_label: 'transposición de rubros', workflow_id: 'resolution.fund_transposition', workflow_version: 2, search_status: 'completed', match_label: 'exact', missing_fields: ['unit'], known_fact_keys: ['expediente'], missing_groups: ['Expediente y unidad'], selected_precedent_number: '2.629/026', selected_precedent_title: 'Resolución N° 2.629/026', selected_precedent_source_url: 'https://example.test/2629', generic_fallback_count: 0, next_action: 'Complete los datos pendientes.' },
    precedent_search: { id: 'search-1', status: 'completed', query: {}, collections: ['validated'], index_status: {}, searched_count: 12, candidates: [], selected_example_version_id: 'example-1', match_label: 'exact', similarities: ['Mismo tipo de movimiento'], differences: ['Otro ejercicio'], errors: [], fallback_reason: null, started_at: '2026-08-17T12:00:00Z', completed_at: '2026-08-17T12:00:01Z' },
    resolved_precedent: { title: 'Resolución N° 2.629/026', number: '2.629/026', date: '2026-01-20', document_type: 'resolución', source_url: 'https://example.test/2629', match_label: 'exact', similarities: ['Mismo tipo de movimiento'], differences: ['Otro ejercicio'], warning: 'Antecedente estructural; sus referencias jurídicas permanecen sin verificar.' },
    question_request: { id: 'question-1', status: 'partial', form_id: 'form-v2', human_task_id: 'task-form', questions: [{ key: 'unit', label: 'Unidad', field_type: 'text', required: true, reason: 'Identifica la unidad.', provenance: { field_key: 'unit', source_type: 'workflow', reason: 'Identifica la unidad.', requires_confirmation: true }, validation_rules: {} }], answers: { unit: 'Hacienda' }, errors: {}, created_at: '2026-08-17T12:00:00Z', updated_at: '2026-08-17T12:05:00Z', answered_at: null },
  })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/api/auth/csrf')) return Response.json({ csrf_token: 'csrf' })
    if (url.includes('/events/stream')) return new Promise((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))
    if (url.endsWith('/workspace')) return Response.json(workspace)
    throw new Error(`Unexpected request ${url}`)
  })
  renderWorkspace('/cases/case-1/intake')
  expect(await screen.findByRole('heading', { name: 'Datos para la trasposición presupuestal' })).toBeVisible()
  expect(screen.getByLabelText(/Unidad solicitante o ejecutora/)).toHaveValue('Hacienda')
  expect(screen.getAllByText('2.629/026').length).toBeGreaterThan(0)
  expect(screen.getByText('Exacta')).toBeVisible()
  expect(screen.getByText('12', { exact: true })).toBeVisible()
  expect(screen.getByText(/Solicitud question-1 · Estado: Parcial · 1 pregunta/)).toBeVisible()
  expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
})
