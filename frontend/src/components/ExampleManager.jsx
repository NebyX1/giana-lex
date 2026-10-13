import { useEffect, useState } from 'react'
import { Button, Card, MessageBar, MessageBarBody, Spinner, Text, Title1 } from '@fluentui/react-components'
import { ArrowLeftRegular, AddRegular, SearchRegular } from '@fluentui/react-icons'
import { examplesApi } from '../api.js'

const labels = {
  preferente: 'Modelo editorial', utilizable_con_ajustes: 'Referencia estructural condicionada',
  no_usar_como_modelo: 'Excluido', pendiente_lectura: 'Pendiente', sin_evaluacion: 'Sin evaluación',
}
const emptyForm = { title: '', text: '', family: '', function: '', origin: '' }

function Lines({ title, values }) {
  if (!values?.length) return null
  return <section className="example-detail-section"><strong>{title}</strong><ul>{values.map((value, index) => <li key={index}>{typeof value === 'string' ? value : <>{value.referencia || value.titulo || ''} {value.articulos?.join(', ') || ''} — {value.estado || (value.texto_completo ? 'texto recuperado' : 'remisión no disponible')}{(value.url || value.url_verificacion) && <> · <a href={value.url || value.url_verificacion} target="_blank" rel="noreferrer">Fuente</a></>}</>}</li>)}</ul></section>
}

export default function ExampleManager({ user, onClose }) {
  const canEdit = user?.is_superuser || user?.roles?.some((role) => ['corpus_curator', 'technical_admin', 'superuser'].includes(role))
  const [filters, setFilters] = useState({ q: '', department: '', family: '', type: '', function: '', date_from: '', date_to: '', decision: '', scope: '', order: 'title', page: 1, page_size: 20 })
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [listing, setListing] = useState({ items: [], total: 0, page: 1 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selected, setSelected] = useState(null)
  const [mode, setMode] = useState('catalog')
  const [form, setForm] = useState(emptyForm)
  const [edit, setEdit] = useState(null)
  const [busy, setBusy] = useState(false)
  const [testQuery, setTestQuery] = useState('')
  const [testResult, setTestResult] = useState(null)
  const [file, setFile] = useState(null)
  const [importResult, setImportResult] = useState(null)

  useEffect(() => { const timer = setTimeout(() => setDebouncedQuery(filters.q), 300); return () => clearTimeout(timer) }, [filters.q])
  useEffect(() => {
    let active = true
    setLoading(true)
    examplesApi.list({ ...filters, q: debouncedQuery }).then((data) => { if (active) setListing(data) })
      .catch((exception) => { if (active) setError(exception.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [filters.department, filters.family, filters.type, filters.function, filters.date_from, filters.date_to, filters.decision, filters.scope, filters.order, filters.page, filters.page_size, debouncedQuery, notice])

  const change = (key, value) => setFilters((old) => ({ ...old, [key]: value, page: 1 }))
  const open = async (id) => {
    try {
      setError('')
      const data = await examplesApi.get(id)
      setSelected(data)
      setEdit({ text: data.active_text, title: data.title, family: data.family, type: data.type, decision: data.decision,
        department: data.department, functions: data.functions.join(', '), scope: data.scope,
        reason: '', promotion_reason: '', resolved_defects: (data.active_metadata?.defectos_resueltos || []).join('\n'),
        enabled_fragments: data.enabled_fragments.join('\n\n'), expected_version: data.version })
      setMode('detail')
    } catch (exception) { setError(exception.message) }
  }
  const create = async () => {
    setBusy(true); setError('')
    try { const data = await examplesApi.create(form); setNotice('Modelo interno guardado como borrador.'); await open(data.id) }
    catch (exception) { setError(exception.message) }
    finally { setBusy(false) }
  }
  const save = async (publish = false, suspend = false, archive = false) => {
    setBusy(true); setError('')
    try {
      const data = await examplesApi.update(selected.id, { ...edit, metadata: { defectos_resueltos: edit.resolved_defects.split('\n').map((v) => v.trim()).filter(Boolean) }, functions: edit.functions.split(',').map((v) => v.trim()).filter(Boolean),
        enabled_fragments: edit.enabled_fragments.split(/\n\s*\n/).map((v) => v.trim()).filter(Boolean), publish, suspend, archive })
      setNotice(publish ? 'Revisión aplicada a Gianna.' : 'Borrador editorial guardado. La revisión activa sigue igual.')
      await open(data.id)
    } catch (exception) { setError(exception.message) }
    finally { setBusy(false) }
  }
  const importFile = async (preview) => {
    if (!file) return
    setBusy(true); setError('')
    try { const data = await examplesApi.importFile(file, preview); setImportResult(data); if (!preview) setNotice(`Importación terminada: ${data.created} creados, ${data.updated} actualizados, ${data.skipped} omitidos, ${data.conflicted} conflictos.`) }
    catch (exception) { setError(exception.message) }
    finally { setBusy(false) }
  }
  const restore = async (revisionId) => {
    setBusy(true); setError('')
    try { const data = await examplesApi.restore(selected.id, revisionId, { expected_version: selected.version, reason: edit.reason || 'Restaurar versión anterior' }); setNotice('Versión restaurada mediante una nueva revisión.'); await open(data.id) }
    catch (exception) { setError(exception.message) }
    finally { setBusy(false) }
  }
  const searchTest = async () => {
    setBusy(true); setError('')
    try { setTestResult(await examplesApi.search(testQuery)) } catch (exception) { setError(exception.message) }
    finally { setBusy(false) }
  }

  return <main className="standalone-page example-page">
    <header className="settings-hero"><Button icon={<ArrowLeftRegular />} onClick={onClose}>Volver a Ajustes</Button><div><Text className="manager-eyebrow" size={100} weight="semibold" block>BIBLIOTECA EDITORIAL</Text><Title1>Resoluciones de ejemplo</Title1><Text className="muted">Referencias para comparar estructura y decisiones. Las citas de otros actos no certifican derecho aplicable.</Text></div></header>
    <nav className="example-tabs" aria-label="Resoluciones de ejemplo">
      {[['catalog', 'Catálogo'], ['create', 'Añadir'], ['import', 'Importar'], ['test', 'Probar búsqueda']].map(([key, title]) => <Button key={key} appearance={mode === key ? 'primary' : 'subtle'} onClick={() => setMode(key)}>{title}</Button>)}
    </nav>
    {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
    {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}

    {mode === 'catalog' && <>
      <div className="example-filters">
        <input aria-label="Buscar ejemplos" placeholder="Buscar título, número o cita" value={filters.q} onChange={(event) => change('q', event.target.value)} />
        <select aria-label="Departamento" value={filters.department} onChange={(event) => change('department', event.target.value)}><option value="">Todos los departamentos</option>{['Lavalleja', 'Montevideo', 'Canelones', 'Maldonado'].map((v) => <option key={v}>{v}</option>)}</select>
        <select aria-label="Calidad editorial" value={filters.decision} onChange={(event) => change('decision', event.target.value)}><option value="">Todas las calidades</option>{Object.entries(labels).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select>
        <select aria-label="Alcance" value={filters.scope} onChange={(event) => change('scope', event.target.value)}><option value="">Todos los alcances</option><option value="editorial">Modelo editorial</option><option value="structure">Sólo estructura</option><option value="excerpt">Fragmentos habilitados</option><option value="none">Sin uso positivo</option></select>
        <input aria-label="Materia" placeholder="Materia" value={filters.family} onChange={(event) => change('family', event.target.value)} />
        <input aria-label="Tipo" placeholder="Tipo" value={filters.type} onChange={(event) => change('type', event.target.value)} />
        <input aria-label="Función" placeholder="Función" value={filters.function} onChange={(event) => change('function', event.target.value)} />
        <label>Desde <input type="date" value={filters.date_from} onChange={(event) => change('date_from', event.target.value)} /></label>
        <label>Hasta <input type="date" value={filters.date_to} onChange={(event) => change('date_to', event.target.value)} /></label>
        <select aria-label="Orden" value={filters.order} onChange={(event) => change('order', event.target.value)}><option value="title">Título</option><option value="act_date">Fecha</option><option value="department">Departamento</option><option value="number">Número</option></select>
      </div>
      <Text>{loading ? 'Cargando…' : `${listing.total} fichas encontradas`}</Text>
      <div className="example-list">{listing.items.map((item) => <Card key={item.id} className="example-list-card"><div><strong>{item.title}</strong><div className="muted">{item.external_id} · {item.department || 'Modelo interno'} · {item.number || 'Sin número oficial'} · {item.type}</div><div>{labels[item.decision] || item.decision} · {item.enabled ? item.scope : 'Fuera de búsqueda positiva'} · revisión {item.revision_id?.slice(0, 8)}</div></div><Button onClick={() => open(item.id)}>Ver y gestionar</Button></Card>)}</div>
      {!loading && !listing.items.length && <Text>No hay fichas con estos filtros.</Text>}
      <div className="knowledge-pagination"><Text>Página {listing.page} de {Math.max(1, Math.ceil(listing.total / filters.page_size))}</Text><div><Button disabled={filters.page <= 1} onClick={() => setFilters((old) => ({ ...old, page: old.page - 1 }))}>Anterior</Button><Button disabled={filters.page * filters.page_size >= listing.total} onClick={() => setFilters((old) => ({ ...old, page: old.page + 1 }))}>Siguiente</Button></div></div>
    </>}

    {mode === 'detail' && selected && <div className="example-detail"><Button onClick={() => setMode('catalog')}>Volver al catálogo</Button><h2>{selected.title}</h2><Text>{labels[selected.decision]} · {selected.scope} · {selected.enabled ? 'Disponible' : 'Suspendido'} · versión {selected.version}</Text><p>{selected.department} · {selected.number || 'Modelo interno'} · {selected.act_date} {selected.url && <a href={selected.url} target="_blank" rel="noreferrer">Fuente original</a>}</p>
      <div className="example-columns"><Card><h3>Original importado</h3><pre>{selected.source_text}</pre></Card><Card><h3>Revisión activa</h3><pre>{selected.active_text}</pre></Card></div>
      <Lines title="Fortalezas" values={selected.fortalezas} /><Lines title="Defectos que no deben repetirse" values={selected.defectos_detectados} /><Lines title="Hechos necesarios" values={selected.hechos_requeridos} /><Lines title="Elementos reutilizables" values={selected.elementos_reutilizables} /><Lines title="Adaptaciones pendientes" values={selected.adaptar_para_lavalleja} /><Lines title="Citas y alcance del cotejo" values={selected.normativa_citada} /><Lines title="Anexos recuperados o remitidos" values={selected.source_metadata?.anexos_recuperados} /><p><strong>Completitud:</strong> {selected.source_metadata?.alcance_completitud || 'No indicada'}</p>
      <section><strong>Historial de revisiones</strong>{selected.history.map((item) => <details key={item.id}><summary>Revisión {item.number} · {item.author} · {item.reason} · {item.scope}</summary><pre>{item.text}</pre>{canEdit && item.id !== selected.revision_id && <Button disabled={busy} onClick={() => restore(item.id)}>Restaurar como nueva revisión</Button>}</details>)}</section>
      {canEdit && <label>Observaciones de origen resueltas (copie cada observación completa en una línea tras corregirla)<textarea rows={5} value={edit.resolved_defects} onChange={(e) => setEdit({ ...edit, resolved_defects: e.target.value })} /></label>}
      {canEdit && <Card className="example-editor"><h3>Editar revisión derivada</h3><label>Título<input value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></label><label>Materia<input value={edit.family} onChange={(e) => setEdit({ ...edit, family: e.target.value })} /></label><label>Tipo<input value={edit.type} onChange={(e) => setEdit({ ...edit, type: e.target.value })} /></label><label>Funciones, separadas por coma<input value={edit.functions} onChange={(e) => setEdit({ ...edit, functions: e.target.value })} /></label><label>Texto derivado<textarea rows={12} value={edit.text} onChange={(e) => setEdit({ ...edit, text: e.target.value })} /></label><label>Fragmentos literales habilitados, separados por línea vacía<textarea rows={4} value={edit.enabled_fragments} onChange={(e) => setEdit({ ...edit, enabled_fragments: e.target.value })} /></label><label>Calidad editorial<select value={edit.decision} onChange={(e) => setEdit({ ...edit, decision: e.target.value })}>{Object.entries(labels).filter(([key]) => key !== 'sin_evaluacion').map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>Alcance<select value={edit.scope} onChange={(e) => setEdit({ ...edit, scope: e.target.value })}><option value="none">Sin uso positivo</option><option value="structure">Sólo estructura</option><option value="editorial">Modelo editorial</option><option value="excerpt">Fragmentos</option></select></label><label>Motivo del cambio<input value={edit.reason} onChange={(e) => setEdit({ ...edit, reason: e.target.value, promotion_reason: e.target.value })} /></label><div className="example-actions"><Button disabled={busy} onClick={() => save(false)}>Guardar borrador</Button><Button appearance="primary" disabled={busy || (selected.decision === 'no_usar_como_modelo' && !edit.reason.trim())} onClick={() => save(true)}>Guardar y aplicar a Gianna</Button><Button disabled={busy} onClick={() => save(true, true)}>Suspender</Button><Button disabled={busy} onClick={() => save(true, false, true)}>Archivar</Button></div></Card>}
    </div>}

    {mode === 'create' && <Card className="example-editor"><h2>Nuevo modelo interno</h2><Text>Se guardará como borrador sin número oficial ni habilitación automática.</Text>{[['title', 'Título'], ['family', 'Materia'], ['function', 'Función'], ['origin', 'Procedencia']].map(([key, label]) => <label key={key}>{label}<input value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} /></label>)}<label>Contenido<textarea rows={15} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></label><Button icon={<AddRegular />} appearance="primary" disabled={!canEdit || busy} onClick={create}>Guardar borrador</Button></Card>}

    {mode === 'import' && <Card className="example-editor"><h2>Importar catálogo</h2><Text>Se admite el HTML con script#dataset, JSON y JSONL. Primero puede previsualizar duplicados y conflictos.</Text><input type="file" accept=".html,.htm,.json,.jsonl" onChange={(e) => setFile(e.target.files?.[0] || null)} /><div className="example-actions"><Button disabled={!canEdit || !file || busy} onClick={() => importFile(true)}>Vista previa</Button><Button appearance="primary" disabled={!canEdit || !file || busy} onClick={() => importFile(false)}>Importar</Button></div>{importResult && <pre>{JSON.stringify(importResult, null, 2)}</pre>}</Card>}

    {mode === 'test' && <Card className="example-editor"><h2>Probar la búsqueda de Gianna</h2><Text>Usa el mismo buscador que la conversación. El puntaje mide pertinencia editorial, no legalidad.</Text><div className="example-actions"><input aria-label="Caso de prueba" value={testQuery} onChange={(e) => setTestQuery(e.target.value)} placeholder="Describa el problema jurídico" /><Button icon={<SearchRegular />} disabled={!testQuery.trim() || busy} onClick={searchTest}>Buscar</Button></div>{busy && <Spinner />}{testResult && <><p>Estado: {testResult.status} · {testResult.total} candidatos · {testResult.duration_ms} ms</p>{testResult.results.map((item) => <Card key={item.id} className="example-list-card"><div><strong>{item.title}</strong><p>{item.external_id} · {item.match_class} · {item.scope} · revisión {item.revision_id}</p><p>{item.reasons.join('; ')}</p>{item.differences.length > 0 && <p>Diferencias: {item.differences.join('; ')}</p>}{item.defectos_detectados?.length > 0 && <p>Defectos: {item.defectos_detectados[0]}</p>}</div>{!item.id.startsWith('legacy:') && <Button onClick={() => open(item.id)}>Abrir</Button>}</Card>)}</>}</Card>}
  </main>
}
