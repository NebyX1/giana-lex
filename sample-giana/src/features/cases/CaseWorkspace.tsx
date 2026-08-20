import { useState } from 'react'
import { Badge, Button, Card, MessageBar, MessageBarBody, Spinner, Text, Textarea, Title1, Title3 } from '@fluentui/react-components'
import { Link, NavLink, useLocation, useParams } from 'react-router-dom'
import { AppIcon } from '../../components/AppIcon'
import { SchemaForm } from '../intake/SchemaForm'
import { IntakeOverview } from '../intake/IntakeOverview'
import { CaseActivityIndicator } from '../workflow/CaseActivityIndicator'
import { CASE_STAGES, caseProgress } from '../workflow/caseProgress'
import { useCaseWorkspace } from '../workflow/useCaseWorkspace'
import { LegalLayout } from './CaseListPage'

export function CaseWorkspace() {
  const { caseId = '' } = useParams()
  const location = useLocation()
  const controller = useCaseWorkspace(caseId)
  const { legalCase, snapshot, workspace, events, loading, error, streamError, refresh } = controller
  const [action, setAction] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [rejection, setRejection] = useState('')

  async function run(type: 'start' | 'retry' | 'cancel') {
    setAction(type); setActionError('')
    try {
      if (type === 'cancel') await controller.cancel('Cancelado desde el workspace')
      else await controller[type]()
    } catch (caught) { setActionError(caught instanceof Error ? caught.message : 'No se pudo ejecutar la acción.') }
    finally { setAction('') }
  }

  async function submitForm(values: Record<string, unknown>, partial = false) {
    if (!workspace?.form) return
    setAction(partial ? 'save-form' : 'submit-form'); setActionError(''); setNotice('')
    try {
      const updated = await controller.submitForm(workspace.form.id, values, partial)
      setNotice(partial ? 'Borrador guardado en el expediente.' : 'Datos registrados. Revise el resumen y confirme los hechos para continuar.')
      return updated
    } catch (caught) { setActionError(caught instanceof Error ? caught.message : 'No se pudieron registrar los datos.') }
    finally { setAction('') }
  }

  async function confirmFacts() {
    const factIds = workspace?.facts.map((fact) => fact.id) ?? []
    if (!factIds.length) return
    setAction('confirm-facts'); setActionError(''); setNotice('')
    try {
      await controller.confirmFacts(factIds)
      setNotice('Hechos confirmados. La investigación jurídica continuó con las fuentes disponibles.')
    } catch (caught) { setActionError(caught instanceof Error ? caught.message : 'No se pudieron confirmar los hechos.') }
    finally { setAction('') }
  }

  async function review(approved: boolean) {
    setAction(approved ? 'approve-review' : 'reject-review'); setActionError(''); setNotice('')
    try {
      await controller.review(approved, approved ? [] : [{
        severity: 'high', category: 'human_review', description: rejection.trim(),
        suggested_action: rejection.trim(), blocks_output: true,
      }])
      setNotice(approved ? 'Revisión humana aprobada.' : 'Se solicitaron cambios sobre el borrador.')
      setRejection('')
    } catch (caught) { setActionError(caught instanceof Error ? caught.message : 'No se pudo registrar la revisión.') }
    finally { setAction('') }
  }

  if (loading) return <LegalLayout><Spinner label="Abriendo expediente" /></LegalLayout>
  if (error || !legalCase || !snapshot || !workspace) return <LegalLayout><MessageBar intent="error"><MessageBarBody>{error || 'Expediente no encontrado.'}</MessageBarBody></MessageBar></LegalLayout>
  const progress = caseProgress(workspace)
  const stage = location.pathname.split('/').at(-1)
  const requestAcceptsAnswers = !workspace.question_request || ['pending', 'partial'].includes(workspace.question_request.status)
  const acceptsAnswers = ['form_ready', 'awaiting_facts'].includes(snapshot.state) && ['open', 'partial'].includes(workspace.form?.status ?? '') && requestAcceptsAnswers
  const canCancel = workspace.capabilities.can_cancel && !['cancelled', 'completed'].includes(snapshot.state)

  return <LegalLayout><Link className="legal-back" to="/cases"><AppIcon name="arrow-left" /> Todos los expedientes</Link>
    <header className="case-header"><div><div className="case-heading-meta"><Badge appearance="filled" color={snapshot.state === 'failed' || snapshot.state === 'cancelled' ? 'danger' : 'informative'}>{snapshot.state.replaceAll('_', ' ')}</Badge><Text>Actualizado {legalCase.updated_at ? new Date(legalCase.updated_at).toLocaleString('es-UY') : 'sin fecha'}</Text></div><Title1 as="h1">{legalCase.title}</Title1><Text className="legal-muted">{workspace.intake_summary?.act_label ?? legalCase.resolution_type ?? legalCase.task_family.replaceAll('_', ' ')} · Riesgo {legalCase.risk_tier}</Text></div><div className="case-actions">{snapshot.state === 'new' && <Button appearance="primary" disabled={Boolean(action)} onClick={() => void run('start')}>Iniciar workflow</Button>}{snapshot.state === 'failed' && <Button appearance="primary" disabled={Boolean(action)} onClick={() => void run('retry')}>Reintentar</Button>}{canCancel && <Button disabled={Boolean(action)} onClick={() => void run('cancel')}>{action === 'cancel' ? <Spinner size="tiny" /> : 'Cancelar'}</Button>}</div></header>
    {actionError && <MessageBar intent="error"><MessageBarBody>{actionError}</MessageBarBody></MessageBar>}
    {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}
    <CaseActivityIndicator workspace={workspace} streamError={streamError} onRefresh={refresh} />
    <IntakeOverview workspace={workspace} />
    <ol className="case-progress" aria-label="Progreso del expediente">{CASE_STAGES.map((label, index) => <li data-status={progress[index]} key={label}><span>{progress[index] === 'complete' ? '✓' : index + 1}</span><Text weight={progress[index] === 'current' ? 'semibold' : 'regular'}>{label}</Text></li>)}</ol>
    <nav className="case-tabs" aria-label="Áreas del expediente"><NavLink end to={`/cases/${caseId}`}>Resumen</NavLink><NavLink to={`/cases/${caseId}/intake`}>Datos</NavLink><NavLink to={`/cases/${caseId}/research`}>Evidencia</NavLink><NavLink to={`/cases/${caseId}/draft`}>Borrador</NavLink><NavLink to={`/cases/${caseId}/review`}>Revisión</NavLink></nav>
    {stage === 'intake' ? <section className="workspace-section"><Title3 as="h2">Datos del expediente</Title3>{acceptsAnswers && workspace.form ? <SchemaForm caseId={caseId} schema={workspace.form.schema_json} initialValues={workspace.form.answers_json} initialStatus={workspace.form.status} initialErrors={workspace.form.errors_json} provenance={workspace.field_provenance} documents={workspace.documents} precedentSourceUrl={workspace.resolved_precedent?.source_url} loading={['save-form', 'submit-form'].includes(action)} onSave={async (values) => { await submitForm(values, true) }} onConfirm={async (values) => (await submitForm(values))?.form?.status === 'submitted'} /> : snapshot.state === 'validating_facts' && workspace.facts.length ? <Card className="fact-confirmation"><Title3 as="h3">Confirme los hechos registrados</Title3><dl className="artifact-data">{workspace.facts.map((fact) => <div key={fact.id}><dt>{fact.key.replaceAll('_', ' ')}</dt><dd>{String(fact.value_json?.value ?? '')}</dd></div>)}</dl><Button appearance="primary" disabled={action === 'confirm-facts'} onClick={() => void confirmFacts()}>{action === 'confirm-facts' ? <Spinner size="tiny" /> : 'Confirmar hechos y continuar'}</Button></Card> : workspace.form ? <Panel title="Datos confirmados" value={workspace.form.answers_json} empty="No hay datos registrados." /> : <EmptyArtifact title="No se pudo cargar el formulario" text="Actualice el expediente. Si persiste, el servidor mostrará un código de seguimiento." />}</section>
      : stage === 'research' ? <div className="workspace-grid"><Panel title="Cuestiones jurídicas" value={workspace.issues} empty="Todavía no hay cuestiones planificadas." /><Panel title="Investigación y Evidence Ledger" value={workspace.evidence} empty="Todavía no hay evidencia verificada." /></div>
        : stage === 'draft' ? <Panel title="Borrador estructurado" value={workspace.draft} empty="El borrador se habilitará cuando la evidencia supere los gates." draft />
          : stage === 'review' ? <div className="workspace-grid"><Card className="artifact-panel"><Title3 as="h2">Revisión humana</Title3><ArtifactValue value={workspace.human_tasks} />{workspace.draft && (workspace.capabilities.can_review || workspace.capabilities.can_reject) && <div className="durable-review-actions"><Text weight="semibold">Draft v{workspace.draft.version}</Text>{workspace.capabilities.can_reject && <Textarea aria-label="Hallazgos para rechazar" value={rejection} onChange={(_, data) => setRejection(data.value)} placeholder="Explique el cambio requerido" />}<div>{workspace.capabilities.can_review && <Button appearance="primary" disabled={Boolean(action)} onClick={() => void review(true)}>Aprobar borrador</Button>}{workspace.capabilities.can_reject && <Button disabled={Boolean(action) || !rejection.trim()} onClick={() => void review(false)}>Rechazar borrador</Button>}</div></div>}</Card><Panel title="Hallazgos" value={workspace.findings} empty="No hay hallazgos registrados." /></div>
             : <div className="workspace-grid"><Panel title="Evidencia" value={workspace.evidence} empty="Investigación pendiente." /><Panel title="Borrador" value={workspace.draft} empty="Aún no se generó un borrador." draft /><Panel title="Actividad reciente" value={events.slice(-6).map((event) => ({ acción: event.event_type, fecha: event.occurred_at }))} empty="Sin actividad nueva en esta conexión." /></div>}
  </LegalLayout>
}

function EmptyArtifact({ title, text }: { title: string; text: string }) { return <div className="artifact-empty"><AppIcon name="history" size={24} /><Text weight="semibold">{title}</Text><Text className="legal-muted">{text}</Text></div> }

function Panel({ title, value, empty, draft }: { title: string; value: unknown; empty: string; draft?: boolean }) {
  return <Card className="artifact-panel"><div className="artifact-title"><Title3 as="h2">{title}</Title3>{draft && <Badge appearance="filled" color="warning">BORRADOR</Badge>}</div>{value === undefined || value === null || (Array.isArray(value) && !value.length) ? <EmptyArtifact title="Sin datos" text={empty} /> : <ArtifactValue value={value} />}</Card>
}

function ArtifactValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) return <ul className="artifact-list">{value.map((item, index) => <li key={index}><ArtifactValue value={item} /></li>)}</ul>
  if (value && typeof value === 'object') return <dl className="artifact-data">{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><ArtifactValue value={item} /></dd></div>)}</dl>
  return <Text>{typeof value === 'boolean' ? value ? 'Sí' : 'No' : String(value)}</Text>
}
