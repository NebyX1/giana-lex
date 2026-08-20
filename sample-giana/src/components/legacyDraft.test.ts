import { expect, test } from 'vitest'
import { parseLegacyDraftContent } from './legacyDraft'

test('mantiene aislado el JSON de resolución legacy', () => {
  const parsed = parseLegacyDraftContent(JSON.stringify({ document_type: 'resolution', title: 'Resolución', vistos: 'Antecedente', resultandos: ['Uno'], considerandos: ['Dos'], atento: 'Ley', resuelve: [{ number: 1, text: 'Dispónese.' }], notes: ['Revisar'] }))
  expect(parsed).toMatchObject({ kind: 'resolution', draft: { title: 'Resolución', resultandos: ['Uno'], considerandos: ['Dos'], resuelve: [{ number: '1', text: 'Dispónese.' }] } })
})

test('acepta documento textual legacy y descarta charla o JSON inválido', () => {
  const document = `RESOLUCIÓN\n\n${'Contenido jurídico suficientemente extenso. '.repeat(8)}\n1. Dispónese la medida.`
  expect(parseLegacyDraftContent(document)).toEqual({ kind: 'text', content: document })
  expect(parseLegacyDraftContent('Respuesta breve del asistente')).toEqual({ kind: 'empty' })
  expect(parseLegacyDraftContent('{mal json')).toEqual({ kind: 'empty' })
})
