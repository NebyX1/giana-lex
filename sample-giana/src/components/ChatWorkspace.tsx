import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import {
  Avatar,
  Badge,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  MessageBar,
  MessageBarBody,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Spinner,
  Text,
  Textarea,
} from '@fluentui/react-components'
import { apiRequest, streamRequest, uploadDocument } from '../api/client'
import type { AgentEvent, Message, PendingQuestion, Provider, Session, Skill, Source, ToolActivity, User } from '../types'
import { useAppStyles } from '../styles'
import { AskUserForm } from './AskUserForm'
import { AdminUsersManager } from './AdminUsersManager'
import { AdminAuditLogManager } from './AdminAuditLogManager'
import { DepartmentalNormsManager } from './DepartmentalNormsManager'
import { NationalNormsManager } from './NationalNormsManager'
import { ProviderManager } from './ProviderManager'
import { RightPanel } from './RightPanel'
import { AppIcon } from './AppIcon'
import { SettingsCenter } from './SettingsCenter'
import { CaseChatFlow } from '../features/cases/CaseChatFlow'
import { caseUiTarget, type CaseUiFocus } from '../features/cases/caseUiAction'
import { activityLabel } from '../features/workflow/caseProgress'
import { useCaseWorkspace } from '../features/workflow/useCaseWorkspace'

type Props = { user: User; providers: Provider[]; setProviders: (providers: Provider[]) => void; darkMode: boolean; onToggleTheme: () => void; onLogout: () => void; initialView?: 'chat' | 'settings' }

const prompts = [
  { eyebrow: 'ANÁLISIS', title: 'Revisar un contrato y detectar riesgos' },
  { eyebrow: 'REDACCIÓN', title: 'Preparar un proyecto de resolución' },
  { eyebrow: 'INVESTIGACIÓN', title: 'Localizar normativa aplicable' },
  { eyebrow: 'EXPEDIENTES', title: 'Ordenar y resumir antecedentes' },
]

function parsePending(raw: string | null): PendingQuestion | null {
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as { questions?: PendingQuestion['questions']; call_id?: string }
    return value.questions ? { callId: value.call_id ?? 'pending', questions: value.questions } : null
  } catch { return null }
}

function parsePersistedSources(toolCalls: NonNullable<Session['tool_calls']>): Source[] {
  const sources = new Map<string, Source>()
  for (const toolCall of toolCalls) {
    if (!toolCall.sources) continue
    try {
      const values = JSON.parse(toolCall.sources) as unknown
      if (!Array.isArray(values)) continue
      for (const value of values) {
        if (!value || typeof value !== 'object') continue
        const raw = value as Record<string, unknown>
        const title = String(raw.title ?? raw.source ?? 'Fuente')
        const source: Source = {
          id: String(raw.id ?? raw.identifier ?? raw.url ?? title),
          title,
          url: raw.url ? String(raw.url) : undefined,
          excerpt: raw.excerpt ? String(raw.excerpt) : undefined,
          category: raw.category ? String(raw.category) : undefined,
          corpus: raw.corpus ? String(raw.corpus) : undefined,
        }
        sources.set(`${source.id}|${source.url ?? ''}`, source)
      }
    } catch { /* Ignore malformed data from legacy conversations. */ }
  }
  return [...sources.values()]
}

export function ChatWorkspace({ user, providers, setProviders, darkMode, onToggleTheme, onLogout, initialView = 'chat' }: Props) {
  const styles = useAppStyles()
  const [sessions, setSessions] = useState<Session[]>([])
  const [archivedSessions, setArchivedSessions] = useState<Session[]>([])
  const [current, setCurrent] = useState<Session | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [tools, setTools] = useState<ToolActivity[]>([])
  const [question, setQuestion] = useState<PendingQuestion | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [providerId, setProviderId] = useState(providers[0]?.id ?? 0)
  const [model, setModel] = useState(providers[0]?.default_model ?? '')
  const [skills, setSkills] = useState<Skill[]>([])
  const [skill, setSkill] = useState('automatic')
  const [input, setInput] = useState('')
  const [attachment, setAttachment] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [caseBusy, setCaseBusy] = useState(false)
  const [error, setError] = useState('')
  const [errorRetryable, setErrorRetryable] = useState(false)
  const [showProviders, setShowProviders] = useState(providers.length === 0)
  const [showNorms, setShowNorms] = useState(false)
  const [showDeptNorms, setShowDeptNorms] = useState(false)
  const [showUsers, setShowUsers] = useState(false)
  const [showSettings, setShowSettings] = useState(initialView === 'settings')
  const [showArchived, setShowArchived] = useState(false)
  const [showAuditLog, setShowAuditLog] = useState(false)
  const [deleteCandidate, setDeleteCandidate] = useState<Session | null>(null)
  const [sessionActionId, setSessionActionId] = useState<number | null>(null)
  const [caseFocus, setCaseFocus] = useState<CaseUiFocus>()
  const messagesContainer = useRef<HTMLDivElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const caseController = useCaseWorkspace(current?.case_id ?? '')

  async function loadSessions() {
    const [active, archived] = await Promise.all([
      apiRequest<{ sessions: Session[] }>('/api/sessions'),
      apiRequest<{ sessions: Session[] }>('/api/sessions/archived'),
    ])
    setSessions(active.sessions)
    setArchivedSessions(archived.sessions)
  }

  async function loadProviders() {
    const response = await apiRequest<{ providers: Provider[] }>('/api/providers')
    setProviders(response.providers)
    if (!providerId && response.providers[0]) setProviderId(response.providers[0].id)
  }

  useEffect(() => {
    void loadSessions().catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'No se pudieron cargar las sesiones.'))
    void apiRequest<{ skills: Skill[] }>('/api/agent/skills').then((response) => setSkills(response.skills)).catch(() => undefined)
  }, [])
  useEffect(() => {
    const container = messagesContainer.current
    if (container) container.scrollTop = container.scrollHeight
  }, [messages, tools, question, current?.id])
  useEffect(() => {
    const refreshAfterOAuth = () => { void loadProviders().catch(() => undefined) }
    window.addEventListener('focus', refreshAfterOAuth)
    return () => window.removeEventListener('focus', refreshAfterOAuth)
  })

  async function openSession(id: number) {
    setError('')
    try {
      const session = await apiRequest<Session>(`/api/sessions/${id}`)
      setCurrent(session); setMessages(session.messages ?? []); setProviderId(session.provider_connection_id); setModel(session.model ?? '')
      setQuestion(parsePending(session.pending_question))
      setTools((session.tool_calls ?? []).filter((tool) => tool.status !== 'skipped').map((tool) => ({ callId: tool.call_id, name: tool.tool_name, status: tool.status, detail: tool.error ?? undefined })))
      setSources(parsePersistedSources(session.tool_calls ?? [])); setShowProviders(false)
      setErrorRetryable(session.status === 'failed')
      if (session.status === 'failed') setError('La ejecución anterior no terminó. Puede continuarla sin repetir la investigación.')
      if (session.status === 'needs_review') setError('La ejecución terminó con observaciones que requieren revisión antes de utilizar el borrador.')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo abrir la conversación.') }
  }

  async function ensureSession(content: string) {
    if (current?.archived_at) throw new Error('Restaure la conversación antes de continuarla.')
    if (current) return current
    if (!providerId) throw new Error('Configure y seleccione un proveedor antes de comenzar.')
    const created = await apiRequest<Session>('/api/sessions', {
      method: 'POST', body: JSON.stringify({ provider_connection_id: providerId, model, title: content.slice(0, 80) }),
    })
    setCurrent(created)
    setSessions((items) => [created, ...items])
    return created
  }

  function handleAgentEvent({ event, data }: AgentEvent) {
    if (event === 'legal.case.linked') {
      const caseId = String(data.case_id ?? '')
      if (caseId) {
        setCurrent((value) => value ? { ...value, case_id: caseId, status: 'awaiting_facts' } : value)
      }
    }
    if (event === 'case.ui.action') {
      const target = caseUiTarget(data.target ?? data.action)
      if (target) setCaseFocus({ target, nonce: Date.now() })
    }
    if (event === 'session.started') {
      setCurrent((value) => value ? { ...value, status: 'running' } : value)
    }
    if (event === 'assistant.delta') setMessages((items) => {
      const next = [...items]
      const last = next.at(-1)
      if (last?.role === 'assistant') next[next.length - 1] = { ...last, content: last.content + String(data.content ?? '') }
      else next.push({ role: 'assistant', content: String(data.content ?? '') })
      return next
    })
    if (event === 'assistant.completed' && data.message) {
      const persisted = data.message as Message
      setMessages((items) => {
        const next = [...items]
        if (next.at(-1)?.role === 'assistant') next[next.length - 1] = persisted
        else next.push(persisted)
        return next
      })
    }
    if (event === 'tool.started') setTools((items) => [...items, { callId: String(data.call_id), name: String(data.tool_name), status: 'running' }])
    if (event === 'tool.completed' || event === 'tool.failed') setTools((items) => items.map((tool) => tool.callId === String(data.call_id) ? { ...tool, status: event === 'tool.completed' ? 'completed' : 'failed', detail: data.message ? String(data.message) : undefined } : tool))
    if (event === 'tool.skipped') setTools((items) => items.filter((tool) => tool.callId !== String(data.call_id)))
    if (event === 'question.created') setQuestion({ callId: String(data.call_id), questions: data.questions as PendingQuestion['questions'] })
    if (event === 'question.answered') setQuestion(null)
    if (event === 'source' || event === 'source.created' || event === 'source.found') {
      const source = data.source && typeof data.source === 'object' ? data.source as Record<string, unknown> : data
      setSources((items) => [...items, { id: String(source.id ?? crypto.randomUUID()), title: String(source.title ?? 'Fuente'), url: source.url ? String(source.url) : undefined, excerpt: source.excerpt ? String(source.excerpt) : undefined, category: source.category ? String(source.category) : undefined, corpus: source.corpus ? String(source.corpus) : undefined }])
    }
    if (event === 'agent.completed') {
      const terminalStatus = String(data.status ?? 'completed')
      setCurrent((value) => value ? { ...value, status: terminalStatus } : value)
      setErrorRetryable(false)
      if (terminalStatus === 'needs_review') setError('El borrador requiere revisión antes de utilizarse.')
    }
    if (event === 'error') {
      setError(String(data.message ?? 'El agente encontró un error.'))
      setErrorRetryable(Boolean(data.retryable))
      setCurrent((value) => value ? { ...value, status: 'failed' } : value)
    }
  }

  async function run(content: string) {
    if (!content.trim() || busy || caseBusy) return
    setBusy(true); setError(''); setErrorRetryable(false); setInput(''); setAttachment(null)
    try {
      const session = await ensureSession(content)
      if (attachment) {
        const uploaded = await uploadDocument(session.id, attachment)
        content = `${content}\n\nDocumento adjunto disponible para tools: document_id=${uploaded.id}, nombre=${uploaded.filename}.`
      }
      setMessages((items) => [...items, { role: 'user', content }])
      await streamRequest(`/api/agent/sessions/${session.id}/run`, { content, active_skills: skill === 'automatic' ? [] : [skill] }, handleAgentEvent)
      await loadSessions()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo contactar al agente.') }
    finally { setBusy(false) }
  }

  async function answer(answers: Record<string, string | string[] | boolean>) {
    if (!current) return
    setBusy(true); setError(''); setErrorRetryable(false)
    try {
      await streamRequest(`/api/agent/sessions/${current.id}/answer`, { answers }, handleAgentEvent)
      await loadSessions()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudieron enviar las respuestas.') }
    finally { setBusy(false) }
  }

  async function retry() {
    if (!current || busy) return
    setBusy(true); setError(''); setErrorRetryable(false)
    try {
      await streamRequest(`/api/agent/sessions/${current.id}/retry`, {}, handleAgentEvent)
      await loadSessions()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo reintentar la ejecución.')
      setErrorRetryable(true)
    } finally { setBusy(false) }
  }

  function submit(event: FormEvent) { event.preventDefault(); void run(input) }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void run(input) } }
  function clearCurrent() { setCurrent(null); setMessages([]); setTools([]); setQuestion(null); setSources([]); setInput(''); setError(''); setErrorRetryable(false); setCaseFocus(undefined) }
  function newSession() { clearCurrent(); setShowProviders(false); setShowArchived(false) }

  async function archiveSession(session: Session) {
    setSessionActionId(session.id); setError('')
    try {
      await apiRequest(`/api/sessions/${session.id}/archive`, { method: 'POST' })
      if (current?.id === session.id) clearCurrent()
      await loadSessions()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo archivar la conversación.')
    } finally { setSessionActionId(null) }
  }

  async function restoreSession(session: Session) {
    setSessionActionId(session.id); setError('')
    try {
      await apiRequest(`/api/sessions/${session.id}/restore`, { method: 'POST' })
      if (current?.id === session.id) clearCurrent()
      await loadSessions()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo restaurar la conversación.')
    } finally { setSessionActionId(null) }
  }

  async function deleteSession() {
    if (!deleteCandidate) return
    const session = deleteCandidate
    setSessionActionId(session.id); setError('')
    try {
      await apiRequest(`/api/sessions/${session.id}`, { method: 'DELETE' })
      setDeleteCandidate(null)
      if (current?.id === session.id) clearCurrent()
      await loadSessions()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo eliminar la conversación.')
    } finally { setSessionActionId(null) }
  }

  function sessionRow(session: Session, archived: boolean) {
    return <div className={styles.sessionRow} data-active={current?.id === session.id} key={session.id}>
      <Button className={styles.sessionButton} appearance="subtle" icon={<AppIcon name={archived ? 'archive' : 'chat'} size={15} />} onClick={() => void openSession(session.id)}>{session.title}</Button>
      <Menu>
        <MenuTrigger disableButtonEnhancement><Button className={styles.sessionMenuButton} appearance="subtle" size="small" aria-label={`Acciones para ${session.title}`} icon={<AppIcon name="more" size={16} />} disabled={sessionActionId === session.id} /></MenuTrigger>
        <MenuPopover><MenuList>
          {archived
            ? <MenuItem icon={<AppIcon name="restore" size={16} />} onClick={() => void restoreSession(session)}>Restaurar conversación</MenuItem>
            : <MenuItem icon={<AppIcon name="archive" size={16} />} onClick={() => void archiveSession(session)}>Archivar conversación</MenuItem>}
          <MenuItem icon={<AppIcon name="trash" size={16} />} onClick={() => setDeleteCandidate(session)}>Eliminar definitivamente</MenuItem>
        </MenuList></MenuPopover>
      </Menu>
    </div>
  }

  if (showProviders) return <div className={styles.app}><ProviderManager providers={providers} onChanged={loadProviders} onClose={providers.length ? () => { setShowProviders(false); setShowSettings(true) } : undefined} /></div>

  if (showNorms) return <div className={styles.app}><NationalNormsManager onClose={() => { setShowNorms(false); setShowSettings(true) }} /></div>

  if (showDeptNorms) return <div className={styles.app}><DepartmentalNormsManager onClose={() => { setShowDeptNorms(false); setShowSettings(true) }} /></div>

  if (showUsers) return <div className={styles.app}><AdminUsersManager onClose={() => { setShowUsers(false); setShowSettings(true) }} /></div>

  if (showAuditLog) return <div className={styles.app}><AdminAuditLogManager onClose={() => { setShowAuditLog(false); setShowSettings(true) }} /></div>

  if (showSettings) return <div className={styles.app}><SettingsCenter
    providers={providers}
    providerId={providerId}
    model={model}
    skill={skill}
    skills={skills}
    hasActiveSession={Boolean(current)}
    isSuperuser={Boolean(user.is_superuser)}
    onProviderChange={(provider) => { setProviderId(provider.id); setModel(provider.default_model ?? '') }}
    onModelChange={setModel}
    onSkillChange={setSkill}
    onOpenProviders={() => setShowProviders(true)}
    onOpenNationalNorms={() => setShowNorms(true)}
    onOpenDepartmentalNorms={() => setShowDeptNorms(true)}
    onOpenUsers={() => setShowUsers(true)}
    onOpenAuditLog={() => setShowAuditLog(true)}
    onClose={() => setShowSettings(false)}
  /></div>

  return <main className={styles.shell}>
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        <div className={styles.sidebarBrandMark}>GL</div>
        <div><Text weight="semibold" size={400} block>Giana-Lex</Text><Text className={styles.muted} size={200}>Espacio jurídico</Text></div>
      </div>
      <div className={styles.sidebarActions}>
        <Button className={styles.newConversationButton} appearance="primary" icon={<AppIcon name="plus" />} onClick={newSession}>Nueva consulta</Button>
      </div>
      <nav className={styles.sessionList} aria-label="Conversaciones">
        <div className={styles.sessionListHeading}>
          <Text size={100} weight="semibold" className={styles.navSectionLabel}>{showArchived ? 'CONVERSACIONES ARCHIVADAS' : 'CONVERSACIONES RECIENTES'}</Text>
          <Button appearance="subtle" size="small" icon={<AppIcon name={showArchived ? 'chat' : 'archive'} size={15} />} onClick={() => setShowArchived((value) => !value)}>{showArchived ? 'Recientes' : `Archivados ${archivedSessions.length ? `(${archivedSessions.length})` : ''}`}</Button>
        </div>
        {(showArchived ? archivedSessions : sessions).length === 0 && <Text className={styles.emptySessions} size={200}>{showArchived ? 'No hay conversaciones archivadas.' : 'Sus consultas aparecerán aquí.'}</Text>}
        {showArchived ? archivedSessions.map((session) => sessionRow(session, true)) : sessions.map((session) => sessionRow(session, false))}
      </nav>
      <div className={styles.sidebarFooter}>
        <div className={styles.sidebarUtilities}>
          <Button className={styles.utilityButton} appearance="subtle" icon={<AppIcon name="settings" />} onClick={() => setShowSettings(true)}>Configuración</Button>
          <Button className={styles.utilityButton} appearance="subtle" icon={<AppIcon name={darkMode ? 'sun' : 'moon'} />} onClick={onToggleTheme}>{darkMode ? 'Modo claro' : 'Modo noche'}</Button>
        </div>
        <div className={styles.userRow}><Avatar name={user.display_name} color="brand" size={36} /><div className={styles.userInfo}><Text block weight="semibold">{user.display_name}</Text><Text block size={200} className={styles.muted}>{user.email}</Text></div><Button appearance="subtle" icon={<AppIcon name="logout" />} aria-label="Cerrar sesión" title="Cerrar sesión" onClick={onLogout} /></div>
      </div>
    </aside>
    <section className={styles.workspace}>
      <header className={styles.topbar}>
        <div className={styles.topbarTitle}>
          <div className={styles.conversationTitle}><Text block weight="semibold" size={400}>{current?.title ?? 'Nueva consulta jurídica'}</Text>{current?.archived_at && <Badge appearance="tint" color="informative">Archivada</Badge>}</div>
           <div className={styles.workspaceStatus}><span data-busy={busy || caseBusy || caseController.activity?.kind === 'working'} /><Text size={200}>{current?.case_id && caseController.workspace ? activityLabel(caseController.workspace) : caseBusy ? 'Procesando expediente' : busy ? 'Procesando solicitud' : 'Espacio de trabajo listo'}</Text></div>
        </div>
      </header>
      <div className={styles.messages} ref={messagesContainer}>
        {error && <MessageBar intent="error"><MessageBarBody>{error}{errorRetryable && current && !current.archived_at && <Button appearance="primary" size="small" disabled={busy} onClick={() => void retry()}>Reintentar desde el último paso</Button>}</MessageBarBody></MessageBar>}
        {messages.length === 0 && !question ? <div className={styles.welcome}>
          <div className={styles.welcomeIcon}><AppIcon name="spark" size={28} /></div>
          <Text size={700} weight="semibold" block>¿Qué necesita resolver?</Text>
          <Text className={styles.welcomeSummary}>Describa el asunto. Giana organizará la investigación, la redacción y la revisión con trazabilidad de fuentes.</Text>
          <div className={styles.promptGrid}>{prompts.map((prompt) => <Card key={prompt.title} className={styles.promptCard} onClick={() => setInput(prompt.title)}>
            <Text className={styles.promptEyebrow} size={100} weight="semibold">{prompt.eyebrow}</Text>
            <div><Text weight="semibold">{prompt.title}</Text><AppIcon name="chevron" size={15} /></div>
          </Card>)}</div>
        </div> : messages.filter((message) => message.role !== 'tool' && message.content).map((message, index) => <div className={`${styles.messageRow} ${message.role === 'user' ? styles.messageUser : ''}`} key={message.id ? `message-${message.id}` : `optimistic-${index}`}>
          {message.role !== 'user' && <div className={styles.agentAvatar}><AppIcon name="spark" size={16} /></div>}
          <div className={styles.messageContent}>{message.role !== 'user' && <Text className={styles.messageAuthor} size={200} weight="semibold">GIANA · ASISTENTE JURÍDICO</Text>}<div className={`${styles.bubble} ${message.role === 'user' ? styles.userBubble : styles.assistantBubble}`}>{message.content}</div></div>
        </div>)}
        {current?.case_id && <CaseChatFlow controller={caseController} focus={caseFocus} onBusyChange={setCaseBusy} />}
        {tools.map((tool) => <div className={styles.activity} key={tool.callId}>{tool.status === 'running' ? <Spinner size="tiny" /> : <Badge appearance="filled" color={tool.status === 'completed' ? 'success' : tool.status === 'failed' ? 'danger' : 'informative'}>{tool.status === 'completed' ? 'completado' : tool.status === 'failed' ? 'error' : tool.status}</Badge>}<Text size={200}>{tool.name.replaceAll('_', ' ')}{tool.detail ? `: ${tool.detail}` : ''}</Text></div>)}
        {question && !current?.archived_at && <AskUserForm request={question} busy={busy} onSubmit={(answers) => void answer(answers)} />}
      </div>
      <div className={styles.composerWrap}>{current?.archived_at ? <div className={styles.archivedNotice}><div><AppIcon name="archive" /><div><Text weight="semibold" block>Conversación archivada</Text><Text className={styles.muted} size={200}>Restaúrela para continuar escribiendo.</Text></div></div><Button appearance="primary" icon={<AppIcon name="restore" />} disabled={sessionActionId === current.id} onClick={() => void restoreSession(current)}>Restaurar</Button></div> : <form className={styles.composer} onSubmit={submit}>
        {attachment && <div className={styles.attachment}><AppIcon name="document" size={15} /><Text size={200}>{attachment.name}</Text><Button appearance="transparent" size="small" onClick={() => setAttachment(null)}>Quitar</Button></div>}
         <Textarea aria-label="Mensaje para Giana" className={styles.composerInput} appearance="filled-lighter" placeholder={caseBusy ? 'Espere mientras termina el paso del expediente…' : question ? 'Complete el formulario para continuar' : 'Describa el asunto jurídico, los antecedentes y el resultado esperado…'} value={input} disabled={busy || caseBusy || Boolean(question)} onChange={(_, data) => setInput(data.value)} onKeyDown={keyDown} />
         <div className={styles.composerActions}><div><input ref={fileInput} className={styles.hiddenFile} type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setAttachment(event.target.files?.[0] ?? null)} /><Button type="button" appearance="subtle" icon={<AppIcon name="attach" />} disabled={caseBusy} onClick={() => fileInput.current?.click()}>Adjuntar</Button></div><Button className={styles.sendButton} appearance="primary" icon={<AppIcon name="send" />} iconPosition="after" type="submit" disabled={busy || caseBusy || !input.trim() || Boolean(question)}>{busy || caseBusy ? <Spinner size="tiny" /> : 'Enviar consulta'}</Button></div>
      </form>}</div>
    </section>
    {current?.case_id
      ? <RightPanel mode="durable" sources={(caseController.workspace?.evidence ?? []).map((evidence) => ({ id: evidence.id, title: [evidence.norm_id ?? evidence.source_id, evidence.article].filter(Boolean).join(' · '), url: evidence.source_url ?? undefined, excerpt: evidence.exact_text, category: evidence.source_class, corpus: evidence.jurisdiction }))} sessionId={current.id} controller={caseController} focus={caseFocus} />
      : <RightPanel mode="legacy" sources={sources} sessionId={current?.id} draftContent={current && ['completed', 'needs_review'].includes(current.status)
        ? [...messages].reverse().find((message) => message.role === 'assistant' && message.content.trim())?.content
        : undefined} />}
    <Dialog open={Boolean(deleteCandidate)} onOpenChange={(_, data) => { if (!data.open && sessionActionId === null) setDeleteCandidate(null) }}>
      <DialogSurface><DialogBody>
        <DialogTitle>Eliminar conversación definitivamente</DialogTitle>
        <DialogContent>Se eliminarán el historial, las herramientas y los documentos asociados a <strong>{deleteCandidate?.title}</strong>. La acción quedará registrada para auditoría y no puede deshacerse.</DialogContent>
        <DialogActions>
          <Button appearance="secondary" disabled={sessionActionId !== null} onClick={() => setDeleteCandidate(null)}>Cancelar</Button>
          <Button appearance="primary" className={styles.dangerButton} icon={<AppIcon name="trash" />} disabled={sessionActionId !== null} onClick={() => void deleteSession()}>{sessionActionId !== null ? <Spinner size="tiny" /> : 'Eliminar definitivamente'}</Button>
        </DialogActions>
      </DialogBody></DialogSurface>
    </Dialog>
  </main>
}
