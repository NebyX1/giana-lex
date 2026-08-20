import { apiRequest, apiUrl, ApiError } from './client'
import type { FormValue, IntakeSchema } from '../features/intake/schema'

export type TaskFamily = 'legal_question' | 'resolution_drafting' | 'document_review' | 'normative_research' | 'general_conversation'
export type RiskTier = 'low' | 'medium' | 'high' | 'critical'

export type LegalCase = {
  id: string
  owner_user_id: number
  title: string
  task_family: TaskFamily
  resolution_type: string | null
  jurisdiction: string
  risk_tier: RiskTier
  workflow_pack_id: string | null
  workflow_pack_version: number | null
  state: string
  state_version: number
  active_run_id: string | null
  corpus_snapshot_id: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  cancelled_at: string | null
}

export type CaseSnapshot = {
  case_id: string
  state: string
  state_version: number
  last_sequence_number: number
  title: string
  task_family: TaskFamily
  resolution_type: string | null
  jurisdiction: string
  risk_tier: RiskTier
  workflow_pack_id: string | null
  workflow_pack_version: number | null
  active_run_id: string | null
  updated_at: string | null
  data: Record<string, unknown>
}

export type CaseEvent = {
  id: string
  case_id: string
  sequence_number: number
  event_type: string
  payload: Record<string, unknown>
  occurred_at: string
}

export type CreateCaseInput = Pick<LegalCase, 'title' | 'task_family' | 'jurisdiction' | 'risk_tier'> & {
  resolution_type?: string | null
}

export type WorkspaceMessage = { id?: number; role: 'user' | 'assistant' | 'system' | 'tool'; content: string; created_at?: string }
export type WorkspaceFact = {
  id: string
  key: string
  value_json: { value?: unknown }
  value_type: string
  source_type: string
  source_ref?: string | null
  confidence: number
  verification_status: string
  recorded_at: string
  supersedes_id?: string | null
}
export type WorkspaceIssue = {
  issue_id: string
  category: string
  question: string
  relevant_fact_ids: string[]
  candidate_authority_ids: string[]
  required_source_classes: string[]
  risk_level: string
  status: string
}
export type WorkspaceEvidence = {
  id: string
  source_id: string
  source_version: string
  source_class: string
  jurisdiction: string
  norm_id?: string | null
  article?: string | null
  exact_text: string
  source_url?: string | null
  checksum: string
  effective_from?: string | null
  effective_to?: string | null
  active: boolean
  verified_at: string
  verification_method: string
}
export type WorkspaceForm = {
  id: string
  status: string
  version: number
  workflow_pack_id: string
  workflow_pack_version: number
  schema_json: IntakeSchema
  answers_json: Record<string, FormValue>
  errors_json: Record<string, FormServerError>
  created_at: string
  updated_at: string
  submitted_at?: string | null
}

export type FormServerError = string | {
  code?: string
  message?: string
  related_field?: string
  details?: unknown[]
}

export type IntakeIntent = {
  task_family: TaskFamily
  act_type: string
  subtype: string
  jurisdiction: string
  requested_artifact?: string | null
  known_facts: Record<string, unknown>
  unresolved_terms: string[]
  workflow_candidates: Array<{ workflow_id: string; version: number; basis: string }>
  selected_workflow_id?: string | null
  selected_workflow_version?: number | null
  classification_basis: string[]
  clarification_required: boolean
  classifier: 'deterministic' | 'model' | 'unavailable' | 'invalid_model_output'
  classifier_version: string
  provider?: string | null
  model?: string | null
  error?: string | null
  risk_tier: RiskTier
}

export type PrecedentSearch = {
  id: string
  status: 'pending' | 'completed' | 'unavailable' | 'failed' | string
  query: Record<string, unknown>
  collections: unknown[]
  index_status: Record<string, unknown>
  searched_count: number
  candidates: unknown[]
  selected_example_version_id?: string | null
  match_label: 'exact' | 'strong' | 'partial' | 'none'
  similarities: unknown[]
  differences: unknown[]
  errors: unknown[]
  fallback_reason?: string | null
  started_at: string
  completed_at?: string | null
}

export type ResolvedPrecedent = {
  title?: string | null
  number?: string | null
  date?: string | null
  document_type?: string | null
  source_url?: string | null
  match_label: 'exact' | 'strong' | 'partial' | 'none'
  similarities: string[]
  differences: string[]
  warning: string
}

export type IntakeQuestion = {
  key: string
  label: string
  field_type: string
  required: boolean
  reason: string
  provenance: FieldProvenance
  validation_rules: Record<string, unknown>
}

export type QuestionRequest = {
  id: string
  status: 'pending' | 'partial' | 'answered' | 'cancelled'
  form_id?: string | null
  human_task_id?: string | null
  questions: IntakeQuestion[]
  answers: Record<string, FormValue>
  errors: Record<string, FormServerError>
  created_at: string
  updated_at: string
  answered_at?: string | null
}

export type FieldProvenance = {
  id?: string
  field_key: string
  source_type: 'workflow' | 'validated_precedent_structure' | 'user_message' | 'persisted_fact' | 'uploaded_document' | 'user_answer' | string
  source_ref?: string | null
  reason: string
  value_json?: { value?: unknown } | null
  requires_confirmation: boolean
}

export type WorkspaceDocument = {
  id: number
  original_name: string
  mime_type: string
  size_bytes: number
  sha256: string
  created_at: string
}

export type IntakeSummary = {
  act_type: string
  subtype: string
  act_label?: string | null
  workflow_id?: string | null
  workflow_version?: number | null
  search_status: string
  match_label?: string | null
  missing_fields: string[]
  known_fact_keys: string[]
  missing_groups: string[]
  selected_precedent_number?: string | null
  selected_precedent_title?: string | null
  selected_precedent_source_url?: string | null
  generic_fallback_count: number
  next_action: string
}

export type WorkspacePrecedent = {
  id: string
  primary_example_version_id?: string | null
  match_type: string
  confidence: number
  alternatives_json: unknown[]
  differences_json: unknown[]
  fallback_reason?: string | null
  created_at: string
}

export type DraftParagraph = {
  text: string
  fact_ids: string[]
  proposition_ids: string[]
  evidence_ids: string[]
}

export type DurableDraftJson = {
  title: string
  expediente?: string | null
  issuing_body?: string | null
  vistos: DraftParagraph[]
  resultandos: DraftParagraph[]
  considerandos: DraftParagraph[]
  legal_basis: DraftParagraph[]
  operative_articles: DraftParagraph[]
  notifications: string[]
  signature_block?: string | null
  annexes?: string[]
  unresolved_flags?: string[]
}

export type DurableDraftRecord = {
  id: string
  case_id: string
  version: number
  status: string
  draft_json: DurableDraftJson
  validation_json: { errors?: unknown[]; [key: string]: unknown }
  created_at: string
}

export type HumanTaskRecord = {
  id: string
  case_id: string
  task_type: string
  status: string
  payload_json: Record<string, unknown>
  created_at: string
  completed_at?: string | null
}

export type ReviewFindingRecord = {
  id: string
  case_id: string
  draft_version_id: string
  reviewer_type: string
  severity: 'info' | 'warning' | 'high' | 'critical' | string
  category: string
  finding_json: Record<string, unknown>
  blocks_output: boolean
  created_at: string
}

export type CaseCapability =
  | 'can_view_draft'
  | 'can_edit_draft'
  | 'can_review'
  | 'can_reject'
  | 'can_export_docx'
  | 'can_request_second_opinion'
  | 'can_cancel'

export type CaseCapabilities = Record<CaseCapability, boolean>

export type BlockingReason = {
  code: string
  message: string
  category: 'consistency' | 'workflow' | 'capability'
  recoverable: boolean
  artifact_type?: string
  artifact_id?: string
}

export type CaseActivityKind = 'working' | 'waiting_user' | 'waiting_human_review' | 'blocked' | 'failed' | 'completed' | 'idle'

export type CaseActivity = {
  kind: CaseActivityKind
  active_run_id?: string | null
  current_step?: string | null
  started_at?: string | null
  task_type?: string | null
  task_id?: string | null
  draft_version?: number | null
  last_event_sequence?: number | null
  last_event_type?: string | null
  updated_at?: string | null
  message?: string | null
}

export type CaseWorkspaceData = {
  schema_version: number | string
  case: LegalCase
  snapshot: CaseSnapshot
  activity: CaseActivity
  form: WorkspaceForm | null
  precedent: WorkspacePrecedent | null
  intake_intent: IntakeIntent | null
  precedent_search: PrecedentSearch | null
  resolved_precedent: ResolvedPrecedent | null
  question_request: QuestionRequest | null
  field_provenance: FieldProvenance[]
  documents: WorkspaceDocument[]
  intake_summary: IntakeSummary | null
  draft: DurableDraftRecord | null
  facts: WorkspaceFact[]
  issues: WorkspaceIssue[]
  evidence: WorkspaceEvidence[]
  human_tasks: HumanTaskRecord[]
  findings: ReviewFindingRecord[]
  capabilities: CaseCapabilities
  blocking_reasons: BlockingReason[]
  session: { id: number; status: string } | null
  messages: WorkspaceMessage[]
  guidance: string
}

export type HumanReviewFindingInput = {
  severity: 'info' | 'warning' | 'high' | 'critical'
  category: string
  description: string
  suggested_action: string
  blocks_output: boolean
}

export const legalApi = {
  list: (signal?: AbortSignal) => apiRequest<{ cases: LegalCase[] }>('/api/legal/cases', { signal }),
  get: (caseId: string, signal?: AbortSignal) => apiRequest<{ case: LegalCase }>(`/api/legal/cases/${caseId}`, { signal }),
  snapshot: (caseId: string, signal?: AbortSignal) => apiRequest<{ snapshot: CaseSnapshot }>(`/api/legal/cases/${caseId}/snapshot`, { signal }),
  workspace: (caseId: string, signal?: AbortSignal) => apiRequest<CaseWorkspaceData>(`/api/legal/cases/${caseId}/workspace`, { signal }),
  create: (input: CreateCaseInput) => apiRequest<{ case: LegalCase }>('/api/legal/cases', {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify(input),
  }),
  start: (caseId: string) => command(caseId, 'start'),
  retry: (caseId: string) => command(caseId, 'retry'),
  cancel: (caseId: string, reason?: string) => command(caseId, 'cancel', reason ? { reason } : {}),
  submitForm: (caseId: string, formId: string, answers: Record<string, unknown>, partial = false) => apiRequest<{ command_id: string; status: string }>(`/api/legal/cases/${caseId}/commands/submit-form`, {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify({ form_id: formId, answers, partial }),
  }),
  confirmFacts: (caseId: string, factIds: string[]) => apiRequest<{ command_id: string; status: string }>(`/api/legal/cases/${caseId}/commands/confirm-facts`, {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: JSON.stringify({ fact_ids: factIds }),
  }),
  review: (caseId: string, approved: boolean, findings: HumanReviewFindingInput[], draft: Pick<DurableDraftRecord, 'id' | 'version'>, idempotencyKey: string = crypto.randomUUID()) => apiRequest<{ command_id: string; status: string }>(`/api/legal/cases/${caseId}/review`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ approved, findings, draft_id: draft.id, draft_version: draft.version }),
  }),
}

function command(caseId: string, action: 'start' | 'retry' | 'cancel', body?: object) {
  return apiRequest<{ command_id: string; status: string }>(`/api/legal/cases/${caseId}/${action}`, {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: body ? JSON.stringify(body) : undefined,
  })
}

type StreamOptions = {
  signal: AbortSignal
  after?: number
  reconnectDelay?: number
  onEvent: (event: CaseEvent) => void
  onReconnect?: (cursor: number) => void | Promise<void>
  onError?: (error: unknown) => void
}

const wait = (milliseconds: number, signal: AbortSignal) => new Promise<void>((resolve) => {
  const timer = window.setTimeout(resolve, milliseconds)
  signal.addEventListener('abort', () => { window.clearTimeout(timer); resolve() }, { once: true })
})

export async function streamCaseEvents(caseId: string, options: StreamOptions) {
  let cursor = options.after ?? 0
  const seen = new Set<number>()
  while (!options.signal.aborted) {
    try {
      const response = await fetch(apiUrl(`/api/legal/cases/${caseId}/events/stream?after=${cursor}`), {
        credentials: 'include',
        signal: options.signal,
        headers: { Accept: 'text/event-stream', 'Last-Event-ID': String(cursor) },
      })
      if (!response.ok) throw new ApiError(`No se pudo abrir el canal de eventos (${response.status}).`, response.status)
      if (!response.body) throw new ApiError('El servidor no inició el canal de eventos.', 502)
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (!options.signal.aborted) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() ?? ''
        for (const block of blocks) {
          const data = block.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n')
          if (!data) continue
          const event = JSON.parse(data) as CaseEvent
          if (event.sequence_number <= cursor || seen.has(event.sequence_number)) continue
          seen.add(event.sequence_number)
          cursor = event.sequence_number
          options.onEvent(event)
        }
        if (done) break
      }
      if (options.signal.aborted) return
      await options.onReconnect?.(cursor)
    } catch (error) {
      if (options.signal.aborted) return
      options.onError?.(error)
      await options.onReconnect?.(cursor)
    }
    await wait(options.reconnectDelay ?? 1000, options.signal)
  }
}
