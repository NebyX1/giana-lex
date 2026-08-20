import { Badge, Card, Text, Title3 } from '@fluentui/react-components'
import type { CaseWorkspaceData, ResolvedPrecedent } from '../../api/legal'

const matchLabels: Record<string, string> = {
  exact: 'Exacta',
  strong: 'Alta',
  partial: 'Parcial',
  none: 'Sin antecedente',
}

const requestStatusLabels: Record<string, string> = {
  pending: 'Pendiente',
  partial: 'Parcial',
  answered: 'Respondida',
  cancelled: 'Cancelada',
}

const searchStatusLabels: Record<string, string> = {
  pending: 'Pendiente',
  completed: 'Completada',
  unavailable: 'No disponible',
  failed: 'Fallida',
}

const nextActionLabels: Record<string, string> = {
  answer_questions: 'Complete los datos pendientes.',
  confirm_facts: 'Confirme los hechos registrados.',
  resolve_blocker: 'Revise y resuelva la intervención indicada.',
  follow_workflow: 'El workflow continuará desde el estado persistido.',
}

function stringItems(values: unknown[]) {
  return values.filter((value): value is string => typeof value === 'string' && Boolean(value.trim()))
}

function PrecedentCard({ precedent, workspace }: { precedent: ResolvedPrecedent | null; workspace: CaseWorkspaceData }) {
  const search = workspace.precedent_search
  if (!precedent && !search) return null
  const similarities = precedent?.similarities ?? stringItems(search?.similarities ?? [])
  const differences = precedent?.differences ?? stringItems(search?.differences ?? [])
  const match = precedent?.match_label ?? search?.match_label ?? 'none'
  return <Card className="intake-precedent-card" aria-label="Antecedente seleccionado">
    <div className="artifact-title"><div><Text className="legal-eyebrow">ANTECEDENTE</Text><Title3 as="h3">{precedent?.title ?? 'Búsqueda de antecedente estructural'}</Title3></div><Badge appearance="filled" color={match === 'none' ? 'subtle' : match === 'partial' ? 'warning' : 'success'}>{matchLabels[match] ?? 'Sin antecedente'}</Badge></div>
    {precedent && <dl className="artifact-data">
      {precedent.document_type && <div><dt>Tipo de acto</dt><dd>{precedent.document_type.replaceAll('_', ' ')}</dd></div>}
      {precedent.number && <div><dt>Número</dt><dd>{precedent.number}</dd></div>}
      {precedent.date && <div><dt>Fecha</dt><dd>{precedent.date}</dd></div>}
      {precedent.source_url && <div><dt>Fuente</dt><dd><a href={precedent.source_url} target="_blank" rel="noreferrer">Consultar publicación oficial</a></dd></div>}
    </dl>}
    <div className="intake-search-status"><Text>Estado de búsqueda: <strong>{searchStatusLabels[search?.status ?? 'pending'] ?? 'Pendiente'}</strong></Text><Text>Antecedentes revisados: <strong>{search?.searched_count ?? 0}</strong></Text></div>
    {(similarities.length > 0 || differences.length > 0) && <div className="intake-comparison">{similarities.length > 0 && <section><Text weight="semibold">Similitudes</Text><ul>{similarities.map((item) => <li key={item}>{item}</li>)}</ul></section>}{differences.length > 0 && <section><Text weight="semibold">Diferencias</Text><ul>{differences.map((item) => <li key={item}>{item}</li>)}</ul></section>}</div>}
    {precedent?.warning && <Text className="precedent-warning" block>{precedent.warning}</Text>}
  </Card>
}

function Diagnostics({ workspace }: { workspace: CaseWorkspaceData }) {
  if (!import.meta.env.DEV) return null
  const intent = workspace.intake_intent
  const summary = workspace.intake_summary
  const search = workspace.precedent_search
  const request = workspace.question_request
  return <details className="intake-diagnostics"><summary>Diagnóstico de desarrollo</summary><dl className="artifact-data">
    <div><dt>Intento</dt><dd>{intent?.subtype ?? 'sin clasificar'}</dd></div>
    <div><dt>Ruta</dt><dd>{summary?.workflow_id ?? intent?.selected_workflow_id ?? 'sin seleccionar'} · v{summary?.workflow_version ?? intent?.selected_workflow_version ?? '—'}</dd></div>
    <div><dt>Búsqueda</dt><dd>{search?.status ?? 'pending'} · {search?.searched_count ?? 0} revisados · seleccionado {search?.selected_example_version_id ? 'sí' : 'no'}</dd></div>
    <div><dt>Preguntas</dt><dd>{request?.questions.length ?? 0} · precompletadas {summary?.known_fact_keys.length ?? Object.keys(intent?.known_facts ?? {}).length}</dd></div>
    {intent?.classifier && <div><dt>Clasificador</dt><dd>{intent.classifier} · {intent.classifier_version}</dd></div>}
    {(intent?.provider || intent?.model) && <div><dt>Proveedor/modelo</dt><dd>{[intent.provider, intent.model].filter(Boolean).join(' · ')}</dd></div>}
  </dl></details>
}

export function IntakeOverview({ workspace }: { workspace: CaseWorkspaceData }) {
  const summary = workspace.intake_summary
  const request = workspace.question_request
  return <div className="intake-overview">
    {(summary || request || workspace.guidance) && <Card className="intake-summary-card"><div><Text className="legal-eyebrow">SOLICITUD</Text><Title3 as="h2">{summary?.act_label ? `Datos para ${summary.act_label}` : 'Preparación del expediente'}</Title3></div>
      {workspace.guidance && <Text>{workspace.guidance}</Text>}
      {summary && <dl className="artifact-data">
        <div><dt>Actuación</dt><dd>{summary.act_label ?? summary.subtype.replaceAll('_', ' ')}</dd></div>
        <div><dt>Datos conocidos</dt><dd>{summary.known_fact_keys.length}</dd></div>
        <div><dt>Datos pendientes</dt><dd>{summary.missing_fields.length}</dd></div>
        {summary.missing_groups.length > 0 && <div><dt>Secciones pendientes</dt><dd>{summary.missing_groups.join(', ')}</dd></div>}
        <div><dt>Siguiente acción</dt><dd>{nextActionLabels[summary.next_action] ?? summary.next_action}</dd></div>
      </dl>}
      {request && <Text className="question-request-status" data-status={request.status}>Solicitud {request.id} · Estado: {requestStatusLabels[request.status]} · {request.questions.length} {request.questions.length === 1 ? 'pregunta' : 'preguntas'}</Text>}
    </Card>}
    <PrecedentCard precedent={workspace.resolved_precedent} workspace={workspace} />
    <Diagnostics workspace={workspace} />
  </div>
}
