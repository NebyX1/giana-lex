export type CaseUiFocus = { target: 'draft' | 'review' | 'form' | 'blocker'; nonce: number }

export function caseUiTarget(value: unknown): CaseUiFocus['target'] | undefined {
  const requested = String(value ?? '')
  const normalized = requested.startsWith('focus_') ? requested.slice('focus_'.length) : requested
  return normalized === 'draft' || normalized === 'review' || normalized === 'form' || normalized === 'blocker' ? normalized : undefined
}
