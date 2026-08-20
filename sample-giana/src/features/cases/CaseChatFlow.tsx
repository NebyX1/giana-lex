import { useEffect, useRef, useState } from 'react'
import { Badge, Button, Card, MessageBar, MessageBarBody, Spinner, Text, Title3 } from '@fluentui/react-components'
import { SchemaForm } from '../intake/SchemaForm'
import { IntakeOverview } from '../intake/IntakeOverview'
import { CaseActivityIndicator } from '../workflow/CaseActivityIndicator'
import { CASE_STAGES, caseProgress } from '../workflow/caseProgress'
import type { CaseWorkspaceController } from '../workflow/useCaseWorkspace'
import type { CaseUiFocus } from './caseUiAction'

const stateLabels: Record<string, string> = {
  awaiting_facts: 'Esperando datos',
  validating_facts: 'Confirmación de hechos',
  legal_issues_planned: 'Plan de investigación listo',
  researching: 'Investigando fuentes',
  verifying_evidence: 'Verificando evidencia',
  evidence_ready: 'Evidencia verificada',
  drafting: 'Preparando borrador',
  ready_for_human_review: 'Esperando revisión humana',
  blocked: 'Requiere intervención',
  completed: 'Completado',
}

export function CaseChatFlow({ controller, onBusyChange, focus }: { controller: CaseWorkspaceController; onBusyChange?: (busy: boolean) => void; focus?: CaseUiFocus }) {
  const { workspace, loading, error, streamError, refresh, submitForm: submitWorkspaceForm, confirmFacts: confirmWorkspaceFacts } = controller
  const [action, setAction] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    onBusyChange?.(Boolean(action))
    return () => onBusyChange?.(false)
  }, [action, onBusyChange])

  useEffect(() => {
    if (focus?.target !== 'form' && focus?.target !== 'blocker') return
    root.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    root.current?.focus({ preventScroll: true })
  }, [focus])

  if (loading) return <Card className="chat-case-flow"><Spinner label="Preparando el plan del expediente" /></Card>
  if (error || !workspace) return <MessageBar intent="error"><MessageBarBody>{error || 'No se pudo abrir el plan del expediente.'}</MessageBarBody></MessageBar>

  const snapshot = workspace.snapshot
  const progress = caseProgress(workspace)
  const requestAcceptsAnswers = !workspace.question_request || ['pending', 'partial'].includes(workspace.question_request.status)
  const acceptsAnswers = ['form_ready', 'awaiting_facts'].includes(snapshot.state) && ['open', 'partial'].includes(workspace.form?.status ?? '') && requestAcceptsAnswers
  const confirmsFacts = snapshot.state === 'validating_facts' && workspace.facts.length > 0
  const schema = workspace.form?.schema_json
  const factIds = workspace.facts.map((fact) => fact.id)

  async function submitForm(values: Record<string, unknown>, partial: boolean) {
    if (!workspace?.form || !acceptsAnswers) return
    setAction(partial ? 'save' : 'submit'); setActionError(''); setNotice('')
    try {
      const updated = await submitWorkspaceForm(workspace.form.id, values, partial)
      setNotice(partial ? 'Borrador guardado en el expediente.' : 'Datos registrados. Confirme el resumen de hechos para continuar.')
      return updated.form?.status === 'submitted'
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'No se pudieron registrar los datos.')
    } finally { setAction('') }
  }

  async function confirmFacts() {
    setAction('confirm'); setActionError(''); setNotice('')
    try {
      const result = await confirmWorkspaceFacts(factIds)
      setNotice(result.snapshot.state === 'blocked'
        ? 'Hechos confirmados. No hay evidencia suficiente para continuar automáticamente; el expediente requiere intervención.'
        : 'Hechos confirmados. El agente continuó con la investigación y la verificación.')
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'No se pudieron confirmar los hechos.')
    } finally { setAction('') }
  }

  return <Card ref={root} tabIndex={-1} className="chat-case-flow" aria-label="Plan jurídico">
    <div className="chat-case-plan-header"><div><Text className="legal-eyebrow">PLAN DEL EXPEDIENTE</Text><Title3 as="h2">Trabajo jurídico controlado</Title3></div><Badge appearance="tint" color={snapshot.state === 'blocked' ? 'danger' : 'informative'}>{stateLabels[snapshot.state] ?? snapshot.state.replaceAll('_', ' ')}</Badge></div>
    <ol className="chat-case-plan">{CASE_STAGES.map((label, index) => <li data-status={progress[index]} key={label}><span>{progress[index] === 'complete' ? '✓' : index + 1}</span><Text weight={progress[index] === 'current' ? 'semibold' : 'regular'}>{label}</Text></li>)}</ol>
    <CaseActivityIndicator workspace={workspace} streamError={streamError} onRefresh={refresh} />
    <IntakeOverview workspace={workspace} />
    {actionError && <MessageBar intent="error"><MessageBarBody>{actionError}</MessageBarBody></MessageBar>}
    {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}
    {workspace.blocking_reasons.some((reason) => reason.category !== 'capability') && <div className="case-blocking-reasons" aria-label="Motivos de bloqueo">{workspace.blocking_reasons.filter((reason) => reason.category !== 'capability').map((reason) => <MessageBar intent="warning" key={`${reason.code}-${reason.artifact_id ?? ''}`}><MessageBarBody>{reason.message}</MessageBarBody></MessageBar>)}</div>}

    {acceptsAnswers && schema && workspace.form && <div className="chat-case-form"><div className="chat-case-section-heading"><div><Text weight="semibold" size={400}>Información que necesito de usted</Text><Text className="legal-muted" block>Complete solamente datos confirmados. Puede guardar y continuar después.</Text></div><Badge appearance="filled" color="warning">Acción requerida</Badge></div><SchemaForm caseId={workspace.case.id} schema={schema} initialValues={workspace.form.answers_json} initialStatus={workspace.form.status} initialErrors={workspace.form.errors_json} provenance={workspace.field_provenance} documents={workspace.documents} precedentSourceUrl={workspace.resolved_precedent?.source_url} loading={Boolean(action)} onSave={(values) => submitForm(values, true).then(() => undefined)} onConfirm={(values) => submitForm(values, false)} /></div>}

    {confirmsFacts && <div className="chat-case-form"><div className="chat-case-section-heading"><div><Text weight="semibold" size={400}>Confirme los hechos registrados</Text><Text className="legal-muted" block>El workflow no investigará ni redactará hasta que confirme este resumen.</Text></div><Badge appearance="filled" color="warning">Acción requerida</Badge></div><dl className="artifact-data">{workspace.facts.map((fact) => <div key={fact.id}><dt>{fact.key.replaceAll('_', ' ')}</dt><dd>{formatValue(fact.value_json?.value)}</dd></div>)}</dl><Button appearance="primary" disabled={Boolean(action)} onClick={() => void confirmFacts()}>{action === 'confirm' ? <Spinner size="tiny" /> : 'Confirmar hechos y continuar'}</Button></div>}

    {!acceptsAnswers && !confirmsFacts && workspace.form && <details className="chat-case-summary"><summary>Datos aportados y bloqueados para edición</summary><dl className="artifact-data">{Object.entries(workspace.form.answers_json).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{formatValue(value)}</dd></div>)}</dl></details>}
  </Card>
}

function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => typeof item === 'object' && item ? Object.values(item).join(' · ') : String(item)).join('; ')
  if (value && typeof value === 'object') return Object.values(value).join(' · ')
  return String(value ?? '')
}
