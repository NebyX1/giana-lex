import { expect, test } from 'vitest'
import { caseUiTarget } from './caseUiAction'

test('normaliza acciones SSE durable para enfocar la UI', () => {
  expect(caseUiTarget('focus_draft')).toBe('draft')
  expect(caseUiTarget('focus_review')).toBe('review')
  expect(caseUiTarget('form')).toBe('form')
  expect(caseUiTarget('unknown')).toBeUndefined()
})
