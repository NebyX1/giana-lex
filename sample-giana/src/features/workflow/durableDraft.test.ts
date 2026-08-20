import { describe, expect, test } from 'vitest'
import { fixtureDraft } from '../../test/workspaceFixture'
import { adaptDurableDraftToEditorModel } from './durableDraft'

describe('adaptDurableDraftToEditorModel', () => {
  test('preserva identidad, versión, textos y referencias separadas', () => {
    const model = adaptDurableDraftToEditorModel(fixtureDraft)
    expect(model).toMatchObject({ recordId: 'draft-2', caseId: 'case-1', version: 2, expediente: '2026-123', issuingBody: 'Intendencia de Lavalleja' })
    expect(model?.vistos[0]).toEqual({ text: 'Visto el expediente.', factRefs: ['fact-1'], propositionRefs: [], evidenceRefs: ['evidence-1'] })
    expect(model?.resultandos.map((item) => item.text)).toEqual(['Resultando probado.'])
    expect(model?.considerandos.map((item) => item.text)).toEqual(['Considerando la competencia.'])
    expect(model?.legalBasis.map((item) => item.text)).toEqual(['Artículo 33 del TOCAF.'])
    expect(model?.operativeArticles.map((item) => item.text)).toEqual(['Autorízase la renovación.'])
    expect(model?.notifications).toEqual(['Notifíquese a las partes.'])
  })

  test('normaliza solamente campos opcionales ausentes', () => {
    const record = { ...fixtureDraft, draft_json: { ...fixtureDraft.draft_json, expediente: undefined, issuing_body: undefined, signature_block: undefined, annexes: undefined, unresolved_flags: undefined } }
    expect(adaptDurableDraftToEditorModel(record)).toMatchObject({ expediente: null, issuingBody: null, signatureBlock: null, annexes: [], unresolvedFlags: [] })
  })

  test('devuelve null para ausencia o borrador vacío inválido', () => {
    expect(adaptDurableDraftToEditorModel(null)).toBeNull()
    expect(adaptDurableDraftToEditorModel({ id: 'malformed', draft_json: { vistos: 'no-array' } })).toBeNull()
    const empty = { ...fixtureDraft, draft_json: { ...fixtureDraft.draft_json, title: '', vistos: [], resultandos: [], considerandos: [], legal_basis: [], operative_articles: [] } }
    expect(adaptDurableDraftToEditorModel(empty)).toBeNull()
  })
})
