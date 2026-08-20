import { useEffect, useRef, useState } from 'react'
import { Badge, Button, Card, Field, Input, MessageBar, MessageBarBody, Spinner, Text, Textarea } from '@fluentui/react-components'
import { apiRequest, ApiError, downloadFile } from '../api/client'
import type { HumanTaskRecord } from '../api/legal'
import type { Source } from '../types'
import type { CaseUiFocus } from '../features/cases/caseUiAction'
import { hasReachedDraftReady } from '../features/workflow/caseProgress'
import { adaptDurableDraftToEditorModel, type DurableEditorParagraph } from '../features/workflow/durableDraft'
import type { CaseWorkspaceController } from '../features/workflow/useCaseWorkspace'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'
import { initialLegacyDraft, parseLegacyDraftContent, type LegacyResolutionArticle, type LegacyResolutionDraft } from './legacyDraft'

type ListField = 'resultandos' | 'considerandos'
type ResolutionArticle = LegacyResolutionArticle
type ResolutionDraft = LegacyResolutionDraft

type RightPanelProps =
  | { mode: 'legacy'; sources: Source[]; sessionId?: number; draftContent?: string }
  | { mode: 'durable'; sources: Source[]; sessionId?: number; controller: CaseWorkspaceController; focus?: CaseUiFocus }

export function RightPanel(props: RightPanelProps) {
  return props.mode === 'durable'
    ? <DurableRightPanel sources={props.sources} sessionId={props.sessionId} controller={props.controller} focus={props.focus} />
    : <LegacyRightPanel sources={props.sources} sessionId={props.sessionId} draftContent={props.draftContent} />
}

function LegacyRightPanel({ sources, sessionId, draftContent }: { sources: Source[]; sessionId?: number; draftContent?: string }) {
  const styles = useAppStyles()
  const [tab, setTab] = useState<'sources' | 'draft'>('sources')
  const [expanded, setExpanded] = useState(false)
  const [draft, setDraft] = useState<ResolutionDraft>(initialLegacyDraft)
  const [draftKind, setDraftKind] = useState<'empty' | 'resolution' | 'text'>('empty')
  const [textDraft, setTextDraft] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [review, setReview] = useState('')

  useEffect(() => {
    setDraft(initialLegacyDraft)
    setDraftKind('empty')
    setTextDraft('')
    setReview('')
    setError('')
    setTab('sources')
  }, [sessionId])

  useEffect(() => {
    const parsed = parseLegacyDraftContent(draftContent)
    if (parsed.kind === 'empty') {
      setDraftKind('empty')
      setTextDraft('')
      setReview('')
      return
    }
    if (parsed.kind === 'resolution') {
      setDraft(parsed.draft)
      setDraftKind('resolution')
      setTab('draft')
    } else {
      setTextDraft(parsed.content)
      setDraftKind('text')
      setTab('draft')
    }
  }, [draftContent])

  const hasArticles = draft.resuelve.some((article) => article.text.trim())
  const hasDraft = draftKind === 'text' ? Boolean(textDraft.trim()) : draftKind === 'resolution' && hasArticles

  function documentPayload() {
    return {
      document_type: 'resolution',
      title: draft.title.trim() || 'RESOLUCIÓN',
      number: draft.number.trim() || null,
      place: draft.place.trim() || null,
      date: draft.date.trim() || null,
      visto: draft.visto.trim(),
      resultandos: draft.resultandos.map((item) => item.trim()).filter(Boolean),
      considerandos: draft.considerandos.map((item) => item.trim()).filter(Boolean),
      atento: draft.atento.trim(),
      resuelve: draft.resuelve.flatMap((article, index) => article.text.trim() ? [{ number: article.number.trim() || String(index + 1), text: article.text.trim() }] : []),
      notes: draft.notes.trim() ? [draft.notes.trim()] : ['BORRADOR SUJETO A REVISIÓN HUMANA'],
    }
  }

  function updateList(field: ListField, index: number, value: string) {
    setDraft((current) => ({ ...current, [field]: current[field].map((item, itemIndex) => itemIndex === index ? value : item) }))
  }

  function addListItem(field: ListField) {
    setDraft((current) => ({ ...current, [field]: [...current[field], ''] }))
  }

  function removeListItem(field: ListField, index: number) {
    setDraft((current) => ({ ...current, [field]: current[field].filter((_, itemIndex) => itemIndex !== index) }))
  }

  function updateArticle(index: number, patch: Partial<ResolutionArticle>) {
    setDraft((current) => ({ ...current, resuelve: current.resuelve.map((article, articleIndex) => articleIndex === index ? { ...article, ...patch } : article) }))
  }

  function addArticle() {
    setDraft((current) => ({ ...current, resuelve: [...current.resuelve, { number: String(current.resuelve.length + 1), text: '' }] }))
  }

  function removeArticle(index: number) {
    setDraft((current) => ({ ...current, resuelve: current.resuelve.filter((_, articleIndex) => articleIndex !== index).map((article, articleIndex) => ({ ...article, number: String(articleIndex + 1) })) }))
  }

  async function exportDocx() {
    if (!sessionId || !hasDraft) return
    setBusy(true); setError('')
    try {
      const result = await apiRequest<{ filename: string; download_url: string }>(`/api/documents/sessions/${sessionId}/generate-docx`, {
        method: 'POST', body: JSON.stringify(draftKind === 'text' ? { content: textDraft } : { resolution: documentPayload() }),
      })
      await downloadFile(result.download_url, result.filename)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo generar el DOCX.')
    } finally { setBusy(false) }
  }

  async function secondOpinion() {
    if (!sessionId || !hasDraft) return
    setBusy(true); setError('')
    try {
      const result = await apiRequest<{ review: string }>(`/api/agent/sessions/${sessionId}/second-opinion`, {
        method: 'POST', body: JSON.stringify({ draft: draftKind === 'text' ? textDraft : JSON.stringify(documentPayload()) }),
      })
      setReview(result.review)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo obtener la segunda opinión.')
    } finally { setBusy(false) }
  }
  return <aside className={`${styles.rightPanel} ${expanded ? styles.rightPanelExpanded : ''}`}>
    <div className={styles.panelHeader}>
      <div><Text weight="semibold" size={400} block>Panel de trabajo</Text><Text className={styles.muted} size={200}>Evidencia y documento</Text></div>
      <div className={styles.panelHeaderActions}>
        <div className={styles.panelStatus} title="Trazabilidad activa"><span /> Auditado</div>
        <Button className={styles.panelExpandButton} appearance="subtle" size="small" icon={<AppIcon name={expanded ? 'collapse' : 'expand'} />} onClick={() => setExpanded((value) => !value)} aria-label={expanded ? 'Contraer panel' : 'Expandir panel'} title={expanded ? 'Contraer panel' : 'Expandir panel'}>
          {expanded ? 'Contraer' : 'Expandir'}
        </Button>
      </div>
    </div>
    <div className={styles.panelTabs}>
      <Button data-active={tab === 'sources'} appearance="subtle" icon={<AppIcon name="sources" />} onClick={() => setTab('sources')}>Fuentes {sources.length ? `(${sources.length})` : ''}</Button>
      <Button data-active={tab === 'draft'} appearance="subtle" icon={<AppIcon name="document" />} onClick={() => setTab('draft')}>Borrador</Button>
    </div>
    <div className={`${styles.panelBody} ${tab === 'draft' ? styles.draftPanelBody : ''}`}>
      {tab === 'sources' ? sources.length ? sources.map((source) => <Card className={styles.sourceCard} key={source.id}>
        <div className={styles.sourceHeading}><div className={styles.sourceIndex}><AppIcon name="document" size={14} /></div><Text weight="semibold">{source.title}</Text></div>{(source.category || source.corpus) && <Badge appearance="outline">{[source.corpus, source.category].filter(Boolean).join(' · ')}</Badge>}{source.excerpt && <Text className={styles.sourceExcerpt}>{source.excerpt}</Text>}{source.url && <a className={styles.sourceLink} href={source.url} target="_blank" rel="noreferrer">Consultar fuente <AppIcon name="chevron" size={13} /></a>}
      </Card>) : <div className={styles.placeholder}><div className={styles.placeholderIcon}><AppIcon name="sources" size={25} /></div><Text size={500} weight="semibold">Fuentes verificables</Text><Text>Las normas, fallos y documentos utilizados aparecerán aquí con su referencia.</Text></div> : draftKind === 'empty' ? <div className={styles.placeholder}><div className={styles.placeholderIcon}><AppIcon name="document" size={25} /></div><Text size={500} weight="semibold">Borrador pendiente</Text><Text>El documento editable aparecerá aquí cuando el agente termine la investigación, redacción y revisión.</Text></div> : draftKind === 'text' ? <div className={styles.draftWorkspace}>
        <div className={styles.draftHeading}>
          <div className={styles.placeholderIcon}><AppIcon name="document" size={20} /></div>
          <div><Text weight="semibold" size={500} block>Borrador del documento</Text><Text className={styles.muted} size={200}>Salida final editable del agente</Text></div>
          <Badge className={styles.draftBadge} appearance="tint" color="warning">BORRADOR</Badge>
        </div>
        {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
        <Textarea className={styles.textDraftEditor} resize="vertical" value={textDraft} onChange={(_, data) => setTextDraft(data.value)} aria-label="Contenido del borrador" />
        {review && <Card className={styles.reviewCard}><Text weight="semibold" block>Segunda opinión independiente</Text><Text>{review}</Text></Card>}
      </div> : <div className={styles.draftWorkspace}>
        <div className={styles.draftHeading}>
          <div className={styles.placeholderIcon}><AppIcon name="document" size={20} /></div>
          <div><Text weight="semibold" size={500} block>Proyecto de resolución</Text><Text className={styles.muted} size={200}>Editor documental guiado</Text></div>
          <Badge className={styles.draftBadge} appearance="tint" color="warning">BORRADOR</Badge>
        </div>
        <Text className={styles.panelHelp} block>Complete las secciones del documento. La estructura técnica se genera automáticamente al exportar.</Text>
        {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}

        <div className={styles.draftForm}>
          <section className={styles.draftSection}>
            <div className={styles.draftSectionHeading}><span>01</span><div><Text weight="semibold" block>Identificación</Text><Text className={styles.muted} size={200}>Datos de encabezado</Text></div></div>
            <Field label="Título del documento"><Input value={draft.title} onChange={(_, data) => setDraft((current) => ({ ...current, title: data.value }))} /></Field>
            <div className={styles.draftMetaGrid}>
              <Field label="Número"><Input placeholder="Sin asignar" value={draft.number} onChange={(_, data) => setDraft((current) => ({ ...current, number: data.value }))} /></Field>
              <Field label="Fecha"><Input placeholder="dd/mm/aaaa" value={draft.date} onChange={(_, data) => setDraft((current) => ({ ...current, date: data.value }))} /></Field>
            </div>
            <Field label="Lugar"><Input placeholder="Ciudad o localidad" value={draft.place} onChange={(_, data) => setDraft((current) => ({ ...current, place: data.value }))} /></Field>
          </section>

          <section className={styles.draftSection}>
            <div className={styles.draftSectionHeading}><span>02</span><div><Text weight="semibold" block>Antecedentes</Text><Text className={styles.muted} size={200}>Hechos y actuaciones previas</Text></div></div>
            <Field label="Visto"><Textarea className={styles.documentTextarea} resize="vertical" rows={4} placeholder="Describa el asunto que da origen a la resolución…" value={draft.visto} onChange={(_, data) => setDraft((current) => ({ ...current, visto: data.value }))} /></Field>
            <div className={styles.draftListHeading}><Text weight="semibold" size={200}>Resultandos</Text><Button size="small" appearance="subtle" icon={<AppIcon name="plus" size={14} />} onClick={() => addListItem('resultandos')}>Agregar</Button></div>
            {draft.resultandos.map((item, index) => <div className={styles.draftListItem} key={`resultando-${index}`}>
              <div><span>{index + 1}</span><Text size={200} weight="semibold">Resultando</Text>{draft.resultandos.length > 1 && <Button size="small" appearance="transparent" onClick={() => removeListItem('resultandos', index)}>Quitar</Button>}</div>
              <Textarea className={styles.documentTextarea} resize="vertical" rows={3} placeholder="Consigne un antecedente relevante…" value={item} onChange={(_, data) => updateList('resultandos', index, data.value)} />
            </div>)}
          </section>

          <section className={styles.draftSection}>
            <div className={styles.draftSectionHeading}><span>03</span><div><Text weight="semibold" block>Fundamentos</Text><Text className={styles.muted} size={200}>Motivación jurídica</Text></div></div>
            <div className={styles.draftListHeading}><Text weight="semibold" size={200}>Considerandos</Text><Button size="small" appearance="subtle" icon={<AppIcon name="plus" size={14} />} onClick={() => addListItem('considerandos')}>Agregar</Button></div>
            {draft.considerandos.map((item, index) => <div className={styles.draftListItem} key={`considerando-${index}`}>
              <div><span>{index + 1}</span><Text size={200} weight="semibold">Considerando</Text>{draft.considerandos.length > 1 && <Button size="small" appearance="transparent" onClick={() => removeListItem('considerandos', index)}>Quitar</Button>}</div>
              <Textarea className={styles.documentTextarea} resize="vertical" rows={3} placeholder="Desarrolle un fundamento normativo o jurídico…" value={item} onChange={(_, data) => updateList('considerandos', index, data.value)} />
            </div>)}
            <Field label="Atento"><Textarea className={styles.documentTextarea} resize="vertical" rows={3} placeholder="Indique las normas y competencias aplicables…" value={draft.atento} onChange={(_, data) => setDraft((current) => ({ ...current, atento: data.value }))} /></Field>
          </section>

          <section className={styles.draftSection}>
            <div className={styles.draftSectionHeading}><span>04</span><div><Text weight="semibold" block>Parte dispositiva</Text><Text className={styles.muted} size={200}>Decisiones que se adoptan</Text></div></div>
            <div className={styles.draftListHeading}><Text weight="semibold" size={200}>Artículos resolutivos</Text><Button size="small" appearance="subtle" icon={<AppIcon name="plus" size={14} />} onClick={addArticle}>Agregar</Button></div>
            {draft.resuelve.map((article, index) => <div className={styles.draftListItem} key={`article-${index}`}>
              <div><span>{article.number || index + 1}</span><Text size={200} weight="semibold">Artículo</Text>{draft.resuelve.length > 1 && <Button size="small" appearance="transparent" onClick={() => removeArticle(index)}>Quitar</Button>}</div>
              <Textarea className={styles.documentTextarea} resize="vertical" rows={3} placeholder="Redacte la decisión o mandato…" value={article.text} onChange={(_, data) => updateArticle(index, { text: data.value })} />
            </div>)}
          </section>

          <section className={styles.draftSection}>
            <div className={styles.draftSectionHeading}><span>05</span><div><Text weight="semibold" block>Control del documento</Text><Text className={styles.muted} size={200}>Advertencias y observaciones</Text></div></div>
            <Field label="Nota de revisión"><Textarea className={styles.documentTextarea} resize="vertical" rows={2} value={draft.notes} onChange={(_, data) => setDraft((current) => ({ ...current, notes: data.value }))} /></Field>
          </section>
        </div>
        {review && <Card className={styles.reviewCard}><Text weight="semibold" block>Segunda opinión independiente</Text><Text>{review}</Text></Card>}
      </div>}
    </div>
    {tab === 'draft' && <div className={styles.panelFooter}><Button appearance="secondary" disabled={!hasDraft || !sessionId || busy} onClick={() => void secondOpinion()}>Revisión independiente</Button><Button appearance="primary" disabled={!hasDraft || !sessionId || busy} onClick={() => void exportDocx()}>Exportar DOCX</Button></div>}
  </aside>
}

function openHumanTask(tasks: HumanTaskRecord[]) {
  return tasks.find((task) => task.task_type === 'review_draft' && ['open', 'pending', 'in_progress', 'waiting'].includes(task.status))
}

function DurableRightPanel({ sources, sessionId, controller, focus }: { sources: Source[]; sessionId?: number; controller: CaseWorkspaceController; focus?: CaseUiFocus }) {
  const styles = useAppStyles()
  const { workspace, refresh, review: submitReview } = controller
  const [tab, setTab] = useState<'sources' | 'draft'>('draft')
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reviewText, setReviewText] = useState('')
  const [rejection, setRejection] = useState('')
  const draftRoot = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setError('')
    setNotice('')
    setReviewText('')
    setRejection('')
    setTab('draft')
  }, [workspace?.case.id])

  useEffect(() => {
    if (!focus || !['draft', 'review', 'blocker'].includes(focus.target)) return
    setTab('draft')
    window.setTimeout(() => {
      draftRoot.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      draftRoot.current?.focus({ preventScroll: true })
    })
  }, [focus, workspace?.case.id])

  const editor = adaptDurableDraftToEditorModel(workspace?.draft)
  useEffect(() => {
    if (workspace?.draft && !editor) console.error('Durable draft schema could not be adapted', { draftId: workspace.draft.id, version: workspace.draft.version })
  }, [editor, workspace?.draft])

  if (!workspace) return <aside className={styles.rightPanel}><div className={styles.placeholder}><Spinner label="Sincronizando expediente" /></div></aside>

  const task = openHumanTask(workspace.human_tasks)
  const completedReview = workspace.human_tasks.find((item) => item.task_type === 'review_draft' && item.status === 'completed')
  const humanFinding = workspace.findings.find((finding) => finding.reviewer_type === 'human')
  const durableSessionId = sessionId ?? workspace.session?.id
  const draftRecord = workspace.draft
  const capabilities = workspace.capabilities
  const inconsistency = hasReachedDraftReady(workspace.snapshot.state) && !workspace.draft
  const preparing = !workspace.draft && (workspace.snapshot.state === 'drafting' || workspace.activity.kind === 'working')
  const invalidDraft = Boolean(workspace.draft && !editor)
  const capabilityReasons = workspace.blocking_reasons.filter((reason) => reason.category === 'capability')
  const workflowReasons = workspace.blocking_reasons.filter((reason) => reason.category !== 'capability')
  const statusText = workspace.activity.kind === 'working' ? 'Trabajando'
    : workspace.activity.kind === 'waiting_human_review' ? 'Revisión humana pendiente'
      : workspace.activity.kind === 'completed' ? 'Revisión completada'
        : workspace.activity.kind === 'blocked' ? 'Cambios solicitados'
          : workspace.activity.kind.replaceAll('_', ' ')

  async function exportDocx() {
    if (!durableSessionId || !capabilities.can_export_docx || !draftRecord) return
    setBusy('docx'); setError(''); setNotice('')
    try {
      const result = await apiRequest<{ filename: string; download_url: string }>(`/api/documents/sessions/${durableSessionId}/generate-docx`, { method: 'POST', body: JSON.stringify({}) })
      await downloadFile(result.download_url, result.filename)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo generar el DOCX persistido.')
    } finally { setBusy('') }
  }

  async function secondOpinion() {
    if (!durableSessionId || !capabilities.can_request_second_opinion || !draftRecord) return
    setBusy('opinion'); setError(''); setNotice('')
    try {
      const result = await apiRequest<{ review: string }>(`/api/agent/sessions/${durableSessionId}/second-opinion`, {
        method: 'POST',
        body: JSON.stringify({ draft_id: draftRecord.id, draft_version: draftRecord.version, draft: JSON.stringify(draftRecord.draft_json) }),
      })
      setReviewText(result.review)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo obtener la segunda opinión IA.')
    } finally { setBusy('') }
  }

  async function review(approved: boolean) {
    if (!draftRecord) return
    setBusy(approved ? 'approve' : 'reject'); setError(''); setNotice('')
    try {
      await submitReview(approved, approved ? [] : [{
        severity: 'high',
        category: 'human_review',
        description: rejection.trim(),
        suggested_action: rejection.trim(),
        blocks_output: true,
      }])
      setNotice(approved ? 'Revisión aprobada y registrada.' : 'Rechazo registrado con sus hallazgos.')
      setRejection('')
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 409
        ? 'El borrador fue actualizado. Recargá la versión más reciente antes de revisarlo.'
        : caught instanceof Error ? caught.message : 'No se pudo registrar la revisión.')
    } finally { setBusy('') }
  }

  return <aside className={`${styles.rightPanel} ${expanded ? styles.rightPanelExpanded : ''}`}>
    <div className={styles.panelHeader}>
      <div><Text weight="semibold" size={400} block>Panel durable</Text><Text className={styles.muted} size={200}>Artefactos persistidos del expediente</Text></div>
      <div className={styles.panelHeaderActions}><div className={styles.panelStatus} title="Estado durable del expediente"><span /> {statusText}</div><Button className={styles.panelExpandButton} appearance="subtle" size="small" icon={<AppIcon name={expanded ? 'collapse' : 'expand'} />} onClick={() => setExpanded((value) => !value)} aria-label={expanded ? 'Contraer panel' : 'Expandir panel'}>{expanded ? 'Contraer' : 'Expandir'}</Button></div>
    </div>
    <div className={styles.panelTabs}>
      <Button data-active={tab === 'sources'} appearance="subtle" icon={<AppIcon name="sources" />} onClick={() => setTab('sources')}>Fuentes {sources.length ? `(${sources.length})` : ''}</Button>
      <Button data-active={tab === 'draft'} appearance="subtle" icon={<AppIcon name="document" />} onClick={() => setTab('draft')}>Borrador {workspace.draft ? `v${workspace.draft.version}` : ''}</Button>
    </div>
    <div className={`${styles.panelBody} ${tab === 'draft' ? styles.draftPanelBody : ''}`}>
      {tab === 'sources' ? <SourceCards sources={sources} styles={styles} /> : <div ref={draftRoot} tabIndex={-1} aria-label="Panel de borrador durable" className={styles.draftWorkspace}>
        {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
        {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}
        {workflowReasons.map((reason) => <MessageBar intent="warning" key={`${reason.code}-${reason.artifact_id ?? ''}`}><MessageBarBody>{reason.message}</MessageBarBody></MessageBar>)}
        {task && <Card className={styles.reviewCard} aria-label="Tarea de revisión humana"><Text weight="semibold" block>Automatización finalizada</Text><Text weight="semibold" block>Esperando revisión humana</Text><Text>Draft v{workspace.draft?.version ?? workspace.activity.draft_version ?? '—'} · tarea {task.status}</Text><Text>Creada {new Date(task.created_at).toLocaleString('es-UY')} · rol requerido: revisor jurídico</Text></Card>}
        {!task && completedReview && workspace.activity.kind === 'completed' && <Card className={styles.reviewCard}><Text weight="semibold" block>Revisión humana aprobada</Text><Text>El expediente está finalizado.</Text></Card>}
        {!task && completedReview && workspace.activity.kind === 'blocked' && <Card className={styles.reviewCard}><Text weight="semibold" block>Se solicitaron cambios</Text><Text>{String(humanFinding?.finding_json.description ?? 'Revise los hallazgos registrados antes de continuar.')}</Text></Card>}

        {!editor && preparing && <div className={styles.placeholder}><Spinner /><Text size={500} weight="semibold">Preparando borrador persistido</Text><Text>La redacción aparecerá cuando se guarde una versión durable.</Text></div>}
        {!editor && inconsistency && <div className={styles.placeholder}><AppIcon name="document" size={25} /><Text size={500} weight="semibold">Estado inconsistente</Text><Text>El workflow informa que el borrador está listo, pero no entregó el artefacto persistido.</Text><Button appearance="primary" disabled={busy === 'sync'} onClick={() => { setBusy('sync'); void refresh().catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'No se pudo sincronizar.')).finally(() => setBusy('')) }}>Reintentar sincronización</Button></div>}
        {invalidDraft && <div className={styles.placeholder}><AppIcon name="document" size={25} /><Text size={500} weight="semibold">No se pudo interpretar el borrador persistido</Text><Text>La versión existe, pero su estructura no coincide con el contrato del editor.</Text><Button appearance="primary" disabled={busy === 'sync'} onClick={() => { setBusy('sync'); void refresh().catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'No se pudo sincronizar.')).finally(() => setBusy('')) }}>Reintentar sincronización</Button></div>}
        {!editor && !preparing && !inconsistency && !invalidDraft && <div className={styles.placeholder}><AppIcon name="document" size={25} /><Text size={500} weight="semibold">Borrador pendiente</Text><Text>El documento se habilitará cuando el workflow persista una versión válida.</Text></div>}
        {editor && <DurableDocument model={editor} />}
        {reviewText && <Card className={styles.reviewCard}><Text weight="semibold" block>Segunda opinión IA</Text><Text>{reviewText}</Text></Card>}
        {editor && task && (workspace.capabilities.can_review || workspace.capabilities.can_reject) && <Card className="durable-review-actions">
          <Text weight="semibold" block>Decisión de revisión humana</Text>
          {workspace.capabilities.can_reject && <Textarea aria-label="Hallazgos para rechazar" placeholder="Explique el hallazgo que debe corregirse" value={rejection} onChange={(_, data) => setRejection(data.value)} />}
          <div>{workspace.capabilities.can_review && <Button appearance="primary" disabled={Boolean(busy)} onClick={() => void review(true)}>Aprobar borrador</Button>}{workspace.capabilities.can_reject && <Button disabled={Boolean(busy) || !rejection.trim()} onClick={() => void review(false)}>Rechazar borrador</Button>}</div>
        </Card>}
      </div>}
    </div>
    {tab === 'draft' && workspace.draft && <><div className={styles.panelFooter}><Button appearance="secondary" disabled={!workspace.capabilities.can_request_second_opinion || !durableSessionId || Boolean(busy)} onClick={() => void secondOpinion()}>Solicitar segunda opinión IA</Button><Button appearance="primary" disabled={!workspace.capabilities.can_export_docx || !durableSessionId || Boolean(busy)} onClick={() => void exportDocx()}>Exportar DOCX</Button></div>{!workspace.capabilities.can_export_docx && capabilityReasons.length > 0 && <div className="case-capability-reasons"><Text weight="semibold" block>La exportación todavía no está disponible:</Text>{capabilityReasons.map((reason) => <Text key={reason.code} block>• {reason.message}</Text>)}</div>}</>}
  </aside>
}

function SourceCards({ sources, styles }: { sources: Source[]; styles: ReturnType<typeof useAppStyles> }) {
  if (!sources.length) return <div className={styles.placeholder}><div className={styles.placeholderIcon}><AppIcon name="sources" size={25} /></div><Text size={500} weight="semibold">Fuentes verificables</Text><Text>Las fuentes persistidas aparecerán aquí.</Text></div>
  return <>{sources.map((source) => <Card className={styles.sourceCard} key={source.id}><div className={styles.sourceHeading}><div className={styles.sourceIndex}><AppIcon name="document" size={14} /></div><Text weight="semibold">{source.title}</Text></div>{source.excerpt && <Text className={styles.sourceExcerpt}>{source.excerpt}</Text>}{source.url && <a className={styles.sourceLink} href={source.url} target="_blank" rel="noreferrer">Consultar fuente</a>}</Card>)}</>
}

function ParagraphSection({ title, paragraphs }: { title: string; paragraphs: DurableEditorParagraph[] }) {
  return <section className="durable-draft-section"><Text weight="semibold" block>{title}</Text>{paragraphs.map((paragraph, index) => <div className="durable-paragraph" key={`${title}-${index}`}><Text>{paragraph.text || '(Párrafo vacío)'}</Text><dl><div><dt>Hechos</dt><dd>{paragraph.factRefs.join(', ') || 'Sin referencias'}</dd></div><div><dt>Proposiciones</dt><dd>{paragraph.propositionRefs.join(', ') || 'Sin referencias'}</dd></div><div><dt>Evidencia</dt><dd>{paragraph.evidenceRefs.join(', ') || 'Sin referencias'}</dd></div></dl></div>)}</section>
}

function DurableDocument({ model }: { model: NonNullable<ReturnType<typeof adaptDurableDraftToEditorModel>> }) {
  return <div className="durable-document" aria-label="Borrador durable">
    <div className="durable-document-heading"><div><Text weight="semibold" size={500} block>{model.title}</Text><Text className="legal-muted">Registro {model.recordId} · versión {model.version} · {model.status}</Text></div><Badge appearance="tint" color="warning">BORRADOR</Badge></div>
    {(model.expediente || model.issuingBody) && <dl className="artifact-data">{model.expediente && <div><dt>Expediente</dt><dd>{model.expediente}</dd></div>}{model.issuingBody && <div><dt>Órgano emisor</dt><dd>{model.issuingBody}</dd></div>}</dl>}
    <ParagraphSection title="Vistos" paragraphs={model.vistos} />
    <ParagraphSection title="Resultandos" paragraphs={model.resultandos} />
    <ParagraphSection title="Considerandos" paragraphs={model.considerandos} />
    <ParagraphSection title="Base jurídica" paragraphs={model.legalBasis} />
    <ParagraphSection title="Artículos resolutivos" paragraphs={model.operativeArticles} />
    <section className="durable-draft-section"><Text weight="semibold" block>Notificaciones</Text>{model.notifications.map((text, index) => <Text key={index} block>{text}</Text>)}</section>
    {model.signatureBlock && <section className="durable-draft-section"><Text weight="semibold" block>Firma</Text><Text>{model.signatureBlock}</Text></section>}
    {model.annexes.length > 0 && <section className="durable-draft-section"><Text weight="semibold" block>Anexos</Text>{model.annexes.map((text, index) => <Text key={index} block>{text}</Text>)}</section>}
    {model.unresolvedFlags.length > 0 && <MessageBar intent="warning"><MessageBarBody>{model.unresolvedFlags.join(' · ')}</MessageBarBody></MessageBar>}
  </div>
}
