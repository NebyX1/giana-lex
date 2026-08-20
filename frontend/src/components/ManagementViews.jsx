import { useState } from 'react'
import { Badge, Button, Card, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Field, Input, Select, Switch, Text, Title1 } from '@fluentui/react-components'
import { AddRegular, ArrowLeftRegular, BookRegular, BotRegular, BuildingRegular, DocumentRegular, HistoryRegular, PeopleRegular, SearchRegular, ShieldCheckmarkRegular } from '@fluentui/react-icons'

const NATIONAL = [
  { id: 1, active: true, identity: 'Ley 18.381', year: '2008', title: 'Derecho de acceso a la información pública', status: 'Indexada', articles: 35 },
  { id: 2, active: true, identity: 'Decreto 232/010', year: '2010', title: 'Reglamentación de acceso a la información pública', status: 'Indexada', articles: 44 },
  { id: 3, active: false, identity: 'Ley 19.355', year: '2015', title: 'Presupuesto nacional de sueldos, gastos e inversiones', status: 'Disponible', articles: 760 },
  { id: 4, active: true, identity: 'TOCAF', year: '2012', title: 'Texto ordenado de contabilidad y administración financiera', status: 'Indexada', articles: 239 },
]

const DEPARTMENTAL = [
  { id: 1, active: true, identity: 'Decreto 3695/2021', year: '2021', title: 'Estatuto del funcionario departamental', family: 'Funcionarios', status: 'Indexada', quality: 'Texto completo', articles: 187 },
  { id: 2, active: true, identity: 'Decreto 3536/2018', year: '2018', title: 'Ordenanza general de tránsito', family: 'Tránsito/SUCIVE', status: 'Indexada', quality: 'Texto completo', articles: 92 },
  { id: 3, active: false, identity: 'Resolución 214/2014', year: '2014', title: 'Régimen de protección del patrimonio departamental', family: 'Patrimonio', status: 'Pendiente de procesar', quality: 'Texto parcial', articles: 14 },
  { id: 4, active: true, identity: 'Decreto 3810/2023', year: '2023', title: 'Regulación de espacios públicos y arbolado', family: 'Espacios', status: 'Indexada', quality: 'Transcripción oficial', articles: 48 },
]

function ManagerHeader({ eyebrow, title, description, onBack, action }) {
  return <header className="manager-header"><Button className="back-button" appearance="secondary" size="large" icon={<ArrowLeftRegular />} onClick={onBack}>Volver a configuración</Button><div className="manager-title-row"><div><Text className="manager-eyebrow" size={100} weight="semibold" block>{eyebrow}</Text><Title1>{title}</Title1><Text className="muted">{description}</Text></div>{action}</div></header>
}

function StatCard({ icon: Icon, label, value }) {
  return <Card className="stat-card"><div className="stat-icon"><Icon /></div><div><Text size={200} className="muted" block>{label}</Text><Text size={600} weight="semibold">{value}</Text></div></Card>
}

export function NormsManager({ kind, onClose }) {
  const departmental = kind === 'departmental'
  const [rows, setRows] = useState(departmental ? DEPARTMENTAL : NATIONAL)
  const [query, setQuery] = useState('')
  const [family, setFamily] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [url, setUrl] = useState('')
  const filtered = rows.filter((row) => `${row.identity} ${row.title} ${row.year} ${row.family || ''}`.toLowerCase().includes(query.toLowerCase()) && (!family || row.family === family))
  const active = rows.filter((row) => row.active).length
  const articles = rows.reduce((total, row) => total + row.articles, 0)
  const toggle = (id) => setRows((current) => current.map((row) => row.id === id ? { ...row, active: !row.active } : row))
  const submitImport = (event) => { event.preventDefault(); setUrl(''); setImportOpen(false) }

  return <section className="standalone-page manager-page">
    <ManagerHeader eyebrow="BIBLIOTECA JURÍDICA" title={`Normativa ${departmental ? 'departamental' : 'nacional'}`} description={departmental ? 'Digesto de Lavalleja organizado por familia normativa y disponibilidad documental.' : 'Normas oficiales disponibles para investigación y fundamentación.'} onBack={onClose} action={<Button appearance="primary" icon={<AddRegular />} onClick={() => setImportOpen(true)}>{departmental ? 'Agregar normativa' : 'Importar desde IMPO'}</Button>} />
    <div className="stats-row"><StatCard icon={BookRegular} label={departmental ? 'Registros' : 'Normas disponibles'} value={rows.length} /><StatCard icon={ShieldCheckmarkRegular} label="Activas para consulta" value={active} /><StatCard icon={DocumentRegular} label="Artículos procesados" value={articles} /><StatCard icon={departmental ? BuildingRegular : SearchRegular} label={departmental ? 'Materias' : 'Indexadas'} value={departmental ? new Set(rows.map((row) => row.family)).size : rows.filter((row) => row.status === 'Indexada').length} /></div>
    <div className="management-toolbar"><Input className="search-field" contentBefore={<SearchRegular />} placeholder="Buscar por nombre, número, tipo o año…" value={query} onChange={(_, data) => setQuery(data.value)} />{departmental && <Select value={family} onChange={(_, data) => setFamily(data.value)}><option value="">Todas las materias</option>{[...new Set(rows.map((row) => row.family))].map((item) => <option key={item}>{item}</option>)}</Select>}<Text className="result-count" size={200}>{filtered.length} resultados</Text></div>
    <div className="table-wrap"><table className="data-table"><thead><tr><th>Activa</th><th>Norma</th><th>Título{departmental ? ' y materia' : ''}</th><th>Estado</th><th>Artículos</th><th>Acciones</th></tr></thead><tbody>{filtered.map((row) => <tr key={row.id}><td><Switch checked={row.active} onChange={() => toggle(row.id)} aria-label={`Activar ${row.title}`} /></td><td><strong>{row.identity}</strong><small>{row.year}</small></td><td className="title-cell"><strong>{row.title}</strong>{row.family && <small>{row.family}</small>}</td><td><div className="status-stack"><Badge appearance="tint" color={row.status === 'Indexada' ? 'success' : 'warning'}>{row.status}</Badge>{row.quality && <Badge appearance="outline" color="informative">{row.quality}</Badge>}</div></td><td>{row.articles}</td><td><Button appearance="secondary" size="small">{departmental ? 'Abrir fuente' : 'Abrir en IMPO'}</Button></td></tr>)}</tbody></table></div>
    <Dialog open={importOpen} onOpenChange={(_, data) => setImportOpen(data.open)}><DialogSurface><form onSubmit={submitImport}><DialogBody><DialogTitle>{departmental ? 'Agregar normativa departamental' : 'Importar normativa desde IMPO'}</DialogTitle><DialogContent className="dialog-form"><div className="dialog-intro"><BookRegular /><Text className="muted">Ingrese el enlace oficial. La integración de persistencia quedará disponible cuando el backend exponga este contrato.</Text></div><Field label="Enlace oficial" required><Input autoFocus value={url} onChange={(_, data) => setUrl(data.value)} placeholder="https://www.impo.com.uy/bases/…" required /></Field></DialogContent><DialogActions><Button type="button" onClick={() => setImportOpen(false)}>Cancelar</Button><Button appearance="primary" type="submit" disabled={!url.trim()}>Validar interfaz</Button></DialogActions></DialogBody></form></DialogSurface></Dialog>
  </section>
}

export function ProviderManager({ onClose }) {
  const [providers, setProviders] = useState([{ id: 1, name: 'Backend actual', type: 'Configuración del servidor', model: 'Modelo predeterminado' }])
  const [form, setForm] = useState({ type: 'featherless', name: '', url: '', model: '' })
  const submit = (event) => { event.preventDefault(); setProviders((items) => [...items, { id: Date.now(), name: form.name, type: form.type, model: form.model || 'Modelo por sesión' }]); setForm({ type: 'featherless', name: '', url: '', model: '' }) }
  return <section className="standalone-page manager-page"><ManagerHeader eyebrow="CONFIGURACIÓN" title="Proveedores de inteligencia artificial" description="Conexiones y modelos disponibles para las consultas jurídicas." onBack={onClose} />
    <Card className="openai-card"><div><Text weight="semibold" size={400} block>Cuenta de OpenAI</Text><Text className="muted">Conecte su cuenta mediante una autorización segura cuando el backend admita este flujo.</Text></div><Button appearance="primary" disabled>Conectar OpenAI</Button></Card>
    <form className="provider-form" onSubmit={submit}><Field label="Tipo"><Select value={form.type} onChange={(_, data) => setForm({ ...form, type: data.value })}><option value="featherless">Featherless</option><option value="ollama">Ollama Cloud</option><option value="custom">API compatible con OpenAI</option></Select></Field><Field label="Nombre" required><Input value={form.name} onChange={(_, data) => setForm({ ...form, name: data.value })} required /></Field><Field label="URL base" required><Input value={form.url} onChange={(_, data) => setForm({ ...form, url: data.value })} required /></Field><Field label="Modelo predeterminado"><Input value={form.model} onChange={(_, data) => setForm({ ...form, model: data.value })} /></Field><Button appearance="primary" type="submit">Agregar a la vista local</Button></form>
    <div className="connection-list"><Text weight="semibold">Conexiones visibles</Text>{providers.map((provider) => <Card className="connection-card" key={provider.id}><div><Text weight="semibold" block>{provider.name}</Text><Text className="muted" size={200}>{provider.type} · {provider.model}</Text></div>{provider.id !== 1 && <Button appearance="subtle" onClick={() => setProviders((items) => items.filter((item) => item.id !== provider.id))}>Eliminar</Button>}</Card>)}</div>
  </section>
}

const INITIAL_USERS = [
  { id: 1, name: 'Administración jurídica', email: 'admin@giana.local', admin: true, active: true, created: '19/08/2026' },
  { id: 2, name: 'Equipo de redacción', email: 'redaccion@giana.local', admin: false, active: true, created: '18/08/2026' },
  { id: 3, name: 'Auditoría', email: 'auditoria@giana.local', admin: false, active: false, created: '15/08/2026' },
]

export function UsersManager({ onClose }) {
  const [users, setUsers] = useState(INITIAL_USERS)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ name: '', email: '' })
  const add = (event) => { event.preventDefault(); setUsers((items) => [...items, { id: Date.now(), ...form, admin: false, active: true, created: new Date().toLocaleDateString('es-UY') }]); setForm({ name: '', email: '' }); setOpen(false) }
  return <section className="standalone-page manager-page"><ManagerHeader eyebrow="ADMINISTRACIÓN" title="Usuarios y permisos" description="Gestione el acceso, estado y rol de las personas habilitadas." onBack={onClose} action={<Button appearance="primary" icon={<AddRegular />} onClick={() => setOpen(true)}>Crear usuario</Button>} /><div className="table-wrap"><table className="data-table"><thead><tr><th>Nombre</th><th>Email</th><th>Rol</th><th>Activo</th><th>Creado</th><th>Acciones</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td><strong>{user.name}</strong></td><td>{user.email}</td><td><Badge appearance="tint" color={user.admin ? 'brand' : 'informative'}>{user.admin ? 'Administrador' : 'Usuario'}</Badge></td><td><Switch checked={user.active} onChange={() => setUsers((items) => items.map((item) => item.id === user.id ? { ...item, active: !item.active } : item))} /></td><td>{user.created}</td><td><Button appearance="subtle" size="small" onClick={() => setUsers((items) => items.map((item) => item.id === user.id ? { ...item, admin: !item.admin } : item))}>{user.admin ? 'Quitar admin' : 'Hacer admin'}</Button></td></tr>)}</tbody></table></div><Dialog open={open} onOpenChange={(_, data) => setOpen(data.open)}><DialogSurface><form onSubmit={add}><DialogBody><DialogTitle>Crear usuario</DialogTitle><DialogContent className="dialog-form"><Field label="Nombre" required><Input value={form.name} onChange={(_, data) => setForm({ ...form, name: data.value })} required /></Field><Field label="Email" required><Input type="email" value={form.email} onChange={(_, data) => setForm({ ...form, email: data.value })} required /></Field></DialogContent><DialogActions><Button type="button" onClick={() => setOpen(false)}>Cancelar</Button><Button appearance="primary" type="submit">Agregar a la vista local</Button></DialogActions></DialogBody></form></DialogSurface></Dialog></section>
}

const AUDIT = [
  ['19/08/2026, 10:42', 'Administración jurídica', 'Inició sesión con segundo factor', 'Cuenta institucional', 'completed', '127.0.0.1'],
  ['19/08/2026, 10:35', 'Equipo de redacción', 'Aprobó un borrador', 'Resolución presupuestal', 'completed', '127.0.0.1'],
  ['19/08/2026, 09:18', 'Sistema', 'Actualizó el índice jurídico', 'Normativa nacional', 'completed', 'local'],
]

export function AuditManager({ onClose }) {
  return <section className="standalone-page manager-page"><ManagerHeader eyebrow="ADMINISTRACIÓN" title="Registro de actividad" description="Trazabilidad de acciones sensibles realizadas dentro del sistema." onBack={onClose} /><div className="stats-row"><StatCard icon={HistoryRegular} label="Eventos visibles" value={AUDIT.length} /><StatCard icon={PeopleRegular} label="Usuarios activos" value="2" /><StatCard icon={BotRegular} label="Origen" value="Local" /></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Fecha y hora</th><th>Usuario</th><th>Acción</th><th>Objeto</th><th>Estado</th><th>Origen</th></tr></thead><tbody>{AUDIT.map((event, index) => <tr key={index}><td>{event[0]}</td><td><strong>{event[1]}</strong></td><td>{event[2]}</td><td>{event[3]}</td><td><Badge appearance="tint" color="success">{event[4]}</Badge></td><td>{event[5]}</td></tr>)}</tbody></table></div></section>
}
