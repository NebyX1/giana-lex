import type { CaseWorkspaceData } from '../../api/legal'

export const CASE_STAGES = ['Solicitud', 'Antecedente', 'Datos', 'Investigación', 'Verificación', 'Borrador', 'Control automático', 'Revisión humana', 'Finalizado'] as const
export type CaseStageStatus = 'complete' | 'current' | 'pending'

const stageByState: Record<string, number> = {
  new: 0,
  intent_compiled: 0,
  workflow_selected: 0,
  searching_precedents: 1,
  precedent_selected: 1,
  form_ready: 2,
  awaiting_facts: 2,
  validating_facts: 2,
  facts_complete: 2,
  legal_issues_planned: 3,
  researching: 3,
  verifying_evidence: 4,
  evidence_ready: 4,
  drafting: 5,
  draft_ready: 5,
  compliance_review: 6,
  citation_review: 6,
  ready_for_human_review: 7,
  completed: 8,
}

export function caseProgress(workspace: CaseWorkspaceData): CaseStageStatus[] {
  if (workspace.snapshot.state === 'completed' || workspace.activity.kind === 'completed') return CASE_STAGES.map(() => 'complete')
  let current = stageByState[workspace.snapshot.state] ?? stageFromActivity(workspace)
  if (current > 5 && !workspace.draft) current = 5
  if (workspace.draft && current < 6) current = 6
  return CASE_STAGES.map((_, index) => index < current ? 'complete' : index === current ? 'current' : 'pending')
}

function stageFromActivity(workspace: CaseWorkspaceData) {
  const step = (workspace.activity.current_step ?? '').toLowerCase()
  if (step.includes('precedent')) return 1
  if (step.includes('form') || step.includes('fact') || step.includes('intake')) return 2
  if (step.includes('research') || step.includes('issue')) return 3
  if (step.includes('evidence') || step.includes('verif')) return 4
  if (step.includes('draft')) return 5
  if (step.includes('compliance') || step.includes('citation')) return 6
  if (step.includes('human') || step.includes('review')) return 7
  if (workspace.draft && (workspace.findings.length > 0 || workspace.human_tasks.some((task) => task.task_type === 'review_draft'))) return 7
  if (workspace.form?.status === 'submitted' || workspace.facts.length > 0) return 3
  return 0
}

export function hasReachedDraftReady(state: string) {
  return (stageByState[state] ?? -1) >= 5 && state !== 'drafting'
}

export function activityLabel(workspace: CaseWorkspaceData) {
  const activity = workspace.activity
  if (activity.message) return activity.message
  const labels = {
    working: 'Procesando expediente',
    waiting_user: 'Esperando datos del usuario',
    waiting_human_review: 'Esperando revisión humana',
    blocked: 'Expediente bloqueado',
    failed: 'El workflow falló',
    completed: 'Expediente finalizado',
    idle: 'Expediente en espera',
  }
  return labels[activity.kind]
}
