import type { DraftParagraph } from '../../api/legal'

export type DurableEditorParagraph = {
  text: string
  factRefs: string[]
  propositionRefs: string[]
  evidenceRefs: string[]
}

export type DurableDraftEditorModel = {
  recordId: string
  caseId: string
  version: number
  status: string
  createdAt: string
  validation: { errors?: unknown[]; [key: string]: unknown }
  title: string
  expediente: string | null
  issuingBody: string | null
  vistos: DurableEditorParagraph[]
  resultandos: DurableEditorParagraph[]
  considerandos: DurableEditorParagraph[]
  legalBasis: DurableEditorParagraph[]
  operativeArticles: DurableEditorParagraph[]
  notifications: string[]
  signatureBlock: string | null
  annexes: string[]
  unresolvedFlags: string[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isParagraph(value: unknown): value is DraftParagraph {
  if (!isRecord(value)) return false
  return typeof value.text === 'string'
    && isStringArray(value.fact_ids)
    && isStringArray(value.proposition_ids)
    && isStringArray(value.evidence_ids)
}

function isParagraphArray(value: unknown): value is DraftParagraph[] {
  return Array.isArray(value) && value.every(isParagraph)
}

function paragraph(value: DraftParagraph): DurableEditorParagraph {
  return {
    text: value.text,
    factRefs: [...value.fact_ids],
    propositionRefs: [...value.proposition_ids],
    evidenceRefs: [...value.evidence_ids],
  }
}

export function adaptDurableDraftToEditorModel(record: unknown): DurableDraftEditorModel | null {
  if (!isRecord(record) || !isRecord(record.draft_json) || !isRecord(record.validation_json)) return null
  const value = record.draft_json
  const sections = [value.vistos, value.resultandos, value.considerandos, value.legal_basis, value.operative_articles]
  if (typeof record.id !== 'string' || typeof record.case_id !== 'string'
    || typeof record.version !== 'number' || typeof record.status !== 'string'
    || typeof record.created_at !== 'string' || typeof value.title !== 'string'
    || !sections.every(isParagraphArray) || !isStringArray(value.notifications)
    || !sections.flat().some((item) => item.text.trim())) return null
  if (value.expediente != null && typeof value.expediente !== 'string') return null
  if (value.issuing_body != null && typeof value.issuing_body !== 'string') return null
  if (value.signature_block != null && typeof value.signature_block !== 'string') return null
  if (value.annexes != null && !isStringArray(value.annexes)) return null
  if (value.unresolved_flags != null && !isStringArray(value.unresolved_flags)) return null

  const [vistos, resultandos, considerandos, legalBasis, operativeArticles] = sections

  return {
    recordId: record.id,
    caseId: record.case_id,
    version: record.version,
    status: record.status,
    createdAt: record.created_at,
    validation: { ...record.validation_json },
    title: value.title,
    expediente: value.expediente ?? null,
    issuingBody: value.issuing_body ?? null,
    vistos: vistos.map(paragraph),
    resultandos: resultandos.map(paragraph),
    considerandos: considerandos.map(paragraph),
    legalBasis: legalBasis.map(paragraph),
    operativeArticles: operativeArticles.map(paragraph),
    notifications: [...value.notifications],
    signatureBlock: value.signature_block ?? null,
    annexes: [...(value.annexes ?? [])],
    unresolvedFlags: [...(value.unresolved_flags ?? [])],
  }
}
