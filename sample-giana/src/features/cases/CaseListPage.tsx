import { useEffect, useState, type FormEvent } from 'react'
import { Badge, Button, Card, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Field, Input, MessageBar, MessageBarBody, Select, Spinner, Text, Title1 } from '@fluentui/react-components'
import { Link, useNavigate } from 'react-router-dom'
import { legalApi, type CreateCaseInput, type LegalCase } from '../../api/legal'
import { AppIcon } from '../../components/AppIcon'

const familyLabel: Record<string, string> = { legal_question: 'Consulta jurídica', resolution_drafting: 'Redacción de resolución', document_review: 'Revisión documental', normative_research: 'Investigación normativa', general_conversation: 'Conversación general' }

export function CaseListPage() {
  const navigate = useNavigate()
  const [cases, setCases] = useState<LegalCase[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [input, setInput] = useState<CreateCaseInput>({ title: '', task_family: 'legal_question', jurisdiction: 'lavalleja', risk_tier: 'low' })

  useEffect(() => {
    const controller = new AbortController()
    void legalApi.list(controller.signal).then((response) => setCases(response.cases)).catch((caught: unknown) => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'No se pudieron cargar los expedientes.') }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  async function create(event: FormEvent) {
    event.preventDefault(); setCreating(true); setError('')
    try { const response = await legalApi.create(input); navigate(`/cases/${response.case.id}`) }
    catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo crear el expediente.') }
    finally { setCreating(false) }
  }

  return <LegalLayout>
    <header className="legal-page-header"><div><Text className="legal-eyebrow">EXPEDIENTES JURÍDICOS</Text><Title1 as="h1">Asuntos en trámite</Title1><Text className="legal-muted">Fuente de verdad durable para datos, evidencia y revisión.</Text></div><Button appearance="primary" size="large" icon={<AppIcon name="plus" />} onClick={() => setOpen(true)}>Nuevo expediente</Button></header>
    {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
    {loading ? <Spinner label="Cargando expedientes" /> : cases.length ? <div className="case-grid">{cases.map((item) => <Link className="case-link" to={`/cases/${item.id}`} key={item.id}><Card className="case-card">
      <div className="case-card-top"><Badge appearance="tint" color={item.state === 'cancelled' || item.state === 'failed' ? 'danger' : item.state === 'completed' ? 'success' : 'informative'}>{item.state.replaceAll('_', ' ')}</Badge><Text size={200}>{new Date(item.updated_at).toLocaleDateString('es-UY')}</Text></div>
      <Text size={500} weight="semibold">{item.title}</Text><Text className="legal-muted">{familyLabel[item.task_family] ?? item.task_family}</Text>
      <div className="case-card-meta"><span>{item.jurisdiction}</span><span>Riesgo {item.risk_tier}</span><AppIcon name="chevron" /></div>
    </Card></Link>)}</div> : <div className="legal-empty"><AppIcon name="document" size={30} /><Title1 as="h1">No hay expedientes</Title1><Text className="legal-muted">Cree el primero para iniciar un workflow jurídico trazable.</Text><Button appearance="primary" onClick={() => setOpen(true)}>Crear expediente</Button></div>}
    <Dialog open={open} onOpenChange={(_, data) => setOpen(data.open)}><DialogSurface><form onSubmit={create}><DialogBody><DialogTitle>Nuevo expediente jurídico</DialogTitle><DialogContent className="create-case-form">
      <Field label="Título" required><Input autoFocus value={input.title} onChange={(_, data) => setInput({ ...input, title: data.value })} /></Field>
      <Field label="Tipo de actuación"><Select value={input.task_family} onChange={(_, data) => setInput({ ...input, task_family: data.value as CreateCaseInput['task_family'] })}>{Object.entries(familyLabel).filter(([key]) => key !== 'general_conversation').map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></Field>
      {input.task_family === 'resolution_drafting' && <Field label="Tipo de resolución"><Input value={input.resolution_type ?? ''} onChange={(_, data) => setInput({ ...input, resolution_type: data.value })} /></Field>}
      <Field label="Jurisdicción"><Input value={input.jurisdiction} onChange={(_, data) => setInput({ ...input, jurisdiction: data.value })} /></Field>
      <Field label="Riesgo"><Select value={input.risk_tier} onChange={(_, data) => setInput({ ...input, risk_tier: data.value as CreateCaseInput['risk_tier'] })}><option value="low">Bajo</option><option value="medium">Medio</option><option value="high">Alto</option><option value="critical">Crítico</option></Select></Field>
    </DialogContent><DialogActions><Button type="button" onClick={() => setOpen(false)}>Cancelar</Button><Button appearance="primary" type="submit" disabled={!input.title.trim() || creating}>{creating ? <Spinner size="tiny" /> : 'Crear expediente'}</Button></DialogActions></DialogBody></form></DialogSurface></Dialog>
  </LegalLayout>
}

export function LegalLayout({ children }: { children: React.ReactNode }) {
  return <main className="legal-shell"><aside className="legal-nav"><Link className="legal-brand" to="/"><span>GL</span><strong>Giana-Lex</strong></Link><nav aria-label="Navegación principal"><Link to="/cases"><AppIcon name="document" />Expedientes</Link><Link to="/"><AppIcon name="chat" />Conversación general</Link><Link to="/settings"><AppIcon name="settings" />Configuración</Link><Link to="/admin"><AppIcon name="shield" />Administración</Link></nav></aside><div className="legal-page">{children}</div></main>
}
