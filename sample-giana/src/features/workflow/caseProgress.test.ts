import { expect, test } from 'vitest'
import { fixtureDraft, makeWorkspace } from '../../test/workspaceFixture'
import { caseProgress } from './caseProgress'

test('no muestra etapas posteriores al borrador sin artefacto persistido', () => {
  const workspace = makeWorkspace({ snapshot: { ...makeWorkspace().snapshot, state: 'ready_for_human_review' }, activity: { kind: 'waiting_human_review' } })
  expect(caseProgress(workspace)).toEqual(['complete', 'complete', 'complete', 'complete', 'complete', 'current', 'pending', 'pending', 'pending'])
})

test('el artefacto durable completa borrador aunque el snapshot esté rezagado', () => {
  const workspace = makeWorkspace({ draft: fixtureDraft })
  expect(caseProgress(workspace)[5]).toBe('complete')
  expect(caseProgress(workspace)[6]).toBe('current')
})

test('completed marca todas las etapas completas', () => {
  const workspace = makeWorkspace({ snapshot: { ...makeWorkspace().snapshot, state: 'completed' }, activity: { kind: 'completed' } })
  expect(caseProgress(workspace).every((status) => status === 'complete')).toBe(true)
})
