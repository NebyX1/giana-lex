import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Badge,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Switch,
  Text,
} from '@fluentui/react-components'
import { apiRequest } from '../api/client'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'
import { ManagerHeader } from './ManagerHeader'

type DeptoNorm = {
  id: string
  norm_id: string
  type: string
  number: string
  year: number | null
  title: string
  normative_family: string
  source_quality: string
  text_available: boolean
  active_for_rag: boolean
  indexed: boolean
  article_count: number
  chunk_count: number
  canonical_source: string
  last_error: string | null
  processing_state?: 'ready' | 'ocr_required' | 'source_without_usable_text' | 'reference_only'
}

type DeptoStats = {
  total: number
  with_text: number
  only_reference: number
  recoverable: number
  reference_only: number
  ocr_required: number
  indexed: number
  active: number
  inactive: number
  articles: number
  chunks: number
  relations: number
  families: number
}

const FAMILY_LABELS: Record<string, string> = {
  estatuto_funcionario: 'Funcionarios',
  procedimiento_administrativo: 'Procedimiento',
  ordenamiento_territorial: 'Territorio',
  patrimonio_departamental: 'Patrimonio',
  interes_departamental: 'Interés',
  interes_cultural_departamental: 'Interés cultural',
  cementerios: 'Cementerios',
  edificacion_arquitectura: 'Arquitectura',
  arbolado_publico: 'Arbolado',
  veredas: 'Veredas',
  tributaria_departamental: 'Tributaria',
  bromatologia: 'Bromatología',
  limpieza_publica: 'Limpieza',
  ruidos_molestos: 'Ruidos',
  transito_sucive: 'Tránsito/SUCIVE',
  zona_azul: 'Zona azul',
  pirotecnia: 'Pirotecnia',
  espacios_publicos: 'Espacios',
  municipios: 'Municipios',
  fideicomiso_departamental: 'Fideicomiso',
  institucion_destacada: 'Institución',
  presupuestos_departamentales: 'Presupuestos',
  general: 'Otros',
}

const qualityLabel = (q: string): { label: string; color: 'success' | 'informative' | 'severe' | 'warning' | 'danger' } => {  if (q === 'primary_full_text') return { label: 'Texto completo', color: 'success' }
  if (q === 'official_republication') return { label: 'Texto completo', color: 'success' }
  if (q === 'official_acta_transcription') return { label: 'Transcripción oficial', color: 'success' }
  if (q === 'primary_partial') return { label: 'Texto parcial', color: 'informative' }
  if (q === 'historical_scan') return { label: 'Histórica', color: 'informative' }
  if (q === 'official_indirect_reference') return { label: 'Original no publicado', color: 'warning' }
  if (q === 'unknown') return { label: 'Pendiente', color: 'severe' }
  return { label: q, color: 'informative' }
}

const statusLabel = (n: DeptoNorm) => {
  if (n.last_error) return { label: 'Error', color: 'danger' as const }
  if (n.processing_state === 'ocr_required') return { label: 'Requiere OCR', color: 'severe' as const }
  if (n.processing_state === 'source_without_usable_text') return { label: 'Fuente sin texto', color: 'severe' as const }
  if (!n.text_available && n.source_quality === 'official_indirect_reference') return { label: 'Original no publicado', color: 'warning' as const }
  if (!n.text_available) return { label: 'Pendiente de procesar', color: 'warning' as const }
  if (!n.active_for_rag) return { label: 'Inactiva', color: 'warning' as const }
  if (n.indexed) return { label: 'Indexada', color: 'success' as const }
  return { label: 'Disponible', color: 'informative' as const }
}

export function DepartmentalNormsManager({ onClose }: { onClose: () => void }) {
  const styles = useAppStyles()
  const [norms, setNorms] = useState<DeptoNorm[]>([])
  const [stats, setStats] = useState<DeptoStats | null>(null)
  const [query, setQuery] = useState('')
  const [family, setFamily] = useState('')
  const [importUrl, setImportUrl] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [importError, setImportError] = useState('')
  const [busy, setBusy] = useState(false)
  const [toggling, setToggling] = useState<string | null>(null)
  const [repairing, setRepairing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async (search?: string) => {
    setError('')
    try {
      const params = new URLSearchParams()
      if (search) params.set('q', search)
      if (family) params.set('family', family)
      const qs = params.toString()
      const response = await apiRequest<{ norms: DeptoNorm[]; stats: DeptoStats }>(`/api/config/normativa/departamental${qs ? `?${qs}` : ''}`)
      setNorms(response.norms)
      setStats(response.stats)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cargar la normativa.')
    }
  }, [family])

  useEffect(() => {
    const handle = setTimeout(() => { void load(query) }, query || family ? 300 : 0)
    return () => clearTimeout(handle)
  }, [family, load, query])

  async function submitImport(event: FormEvent) {
    event.preventDefault()
    if (!importUrl.trim() || busy) return
    setBusy(true); setError(''); setImportError(''); setNotice('')
    try {
      const response = await apiRequest<{ result: { message: string } }>('/api/config/normativa/departamental/import', {
        method: 'POST', body: JSON.stringify({ url: importUrl.trim() }),
      })
      setNotice(response.result.message)
      setImportUrl('')
      setImportOpen(false)
      await load(query)
    } catch (caught) {
      setImportError(caught instanceof Error ? caught.message : 'No se pudo importar la norma.')
    } finally { setBusy(false) }
  }

  async function toggleActive(entry: DeptoNorm) {
    setToggling(entry.id); setError(''); setNotice('')
    try {
      const endpoint = entry.active_for_rag ? 'deactivate' : 'activate'
      await apiRequest(`/api/config/normativa/departamental/${entry.id}/${endpoint}`, { method: 'POST' })
      setNorms((items) => items.map((item) => item.id === entry.id ? { ...item, active_for_rag: !entry.active_for_rag } : item))
      await load(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cambiar el estado.')
    } finally { setToggling(null) }
  }

  async function repairLibrary() {
    if (repairing) return
    setRepairing(true); setError(''); setNotice('')
    try {
      const response = await apiRequest<{ result: { repaired: number; with_text: number; indexed: number; failed: number } }>('/api/config/normativa/departamental/repair-cache', { method: 'POST' })
      const { repaired, with_text, indexed, failed } = response.result
      setNotice(`Se reprocesaron ${repaired} fuentes: ${with_text} con texto recuperado y ${indexed} indexadas.${failed ? ` ${failed} requieren revisión.` : ''}`)
      await load(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo reparar la biblioteca.')
    } finally { setRepairing(false) }
  }

  return (
    <section className={styles.normsManager} aria-label="Normativa departamental">
      <ManagerHeader eyebrow="BIBLIOTECA JURÍDICA" title="Normativa departamental" description="Digesto de Lavalleja organizado por familia normativa y disponibilidad documental." onBack={onClose} actions={<Button appearance="primary" icon={<AppIcon name="download" />} onClick={() => { setImportError(''); setImportOpen(true) }}>Agregar normativa</Button>} />

      {stats && (
        <div className={styles.statsRow}>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="book" /></div><div><Text size={200} className={styles.muted}>Registros</Text><Text size={600} weight="semibold" block>{stats.total}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="shield" /></div><div><Text size={200} className={styles.muted}>Consultables</Text><Text size={600} weight="semibold" block>{stats.active}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="sources" /></div><div><Text size={200} className={styles.muted}>Indexadas</Text><Text size={600} weight="semibold" block>{stats.indexed}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="document" /></div><div><Text size={200} className={styles.muted}>Texto utilizable</Text><Text size={600} weight="semibold" block>{stats.with_text}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="building" /></div><div><Text size={200} className={styles.muted}>Materias</Text><Text size={600} weight="semibold" block>{stats.families}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="chat" /></div><div><Text size={200} className={styles.muted}>Relaciones</Text><Text size={600} weight="semibold" block>{stats.relations}</Text></div></Card>
        </div>
      )}

      {stats && stats.recoverable > 0 && (
        <div className={styles.libraryRepairBanner} role="status">
          <div className={styles.libraryRepairCopy}>
            <div className={styles.placeholderIcon}><AppIcon name="spark" size={20} /></div>
            <div><Text weight="semibold" block>{stats.recoverable} fuentes descargadas necesitan reprocesarse</Text><Text className={styles.muted} size={200}>Los archivos ya están en el equipo; no es necesario volver a buscarlos ni cargarlos manualmente.</Text></div>
          </div>
          <Button appearance="primary" disabled={repairing} onClick={() => void repairLibrary()}>{repairing ? 'Reparando…' : 'Recuperar textos'}</Button>
        </div>
      )}

      {stats && stats.recoverable === 0 && (stats.reference_only > 0 || stats.ocr_required > 0) && (
        <MessageBar intent="info"><MessageBarBody>{stats.reference_only > 0 ? `${stats.reference_only} normas históricas tienen existencia confirmada, pero su texto original no fue localizado en los repositorios oficiales consultados. No están pendientes de proceso: permanecen identificadas como evidencia y no se usan para responder consultas. ` : ''}{stats.ocr_required > 0 ? `${stats.ocr_required} documento escaneado requiere OCR. ` : ''}</MessageBarBody></MessageBar>
      )}

      <div className={styles.managementToolbar}>
        <Input className={styles.searchField} contentBefore={<AppIcon name="search" size={16} />} placeholder="Buscar por número, nombre o materia…" value={query} onChange={(_, data) => setQuery(data.value)} />
        <Select className={styles.familyFilter} aria-label="Filtrar por familia" value={family} onChange={(_, data) => setFamily(data.value)}>
          <option value="">Todas las materias</option>
          {Object.entries(FAMILY_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </Select>
        <Text className={styles.resultCount} size={200}>{norms.length} {norms.length === 1 ? 'resultado' : 'resultados'}</Text>
      </div>

      {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
      {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}

      <div className={styles.normsTableWrap}>
        <table className={styles.normsTable}>
          <thead>
            <tr>
              <th className={styles.normsTableTh}>Activa</th>
              <th className={styles.normsTableTh}>Norma</th>
              <th className={styles.normsTableTh}>Título y materia</th>
              <th className={styles.normsTableTh}>Estado</th>
              <th className={styles.normsTableTh}>Artículos</th>
              <th className={styles.normsTableTh}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {norms.map((entry) => {
              const st = statusLabel(entry)
              const q = qualityLabel(entry.source_quality)
              return (
                <tr className={styles.normsTableRow} key={entry.id}>
                  <td className={styles.normsTableTd}>
                    <Switch checked={entry.active_for_rag} disabled={toggling === entry.id || !entry.text_available} onChange={() => void toggleActive(entry)} aria-label={`Activar ${entry.title}`} />
                  </td>
                  <td className={styles.normsTableTd}>
                    <div className={styles.normIdentity}><Text weight="semibold">{entry.type} {entry.number || 's/n'}</Text><Text className={styles.muted} size={200}>{entry.year ?? 'Año no indicado'}</Text></div>
                  </td>
                  <td className={`${styles.normsTableTd} ${styles.normTitleCell}`} title={entry.title}>
                    <Text weight="semibold" block>{entry.title}</Text><Text className={styles.muted} size={200}>{FAMILY_LABELS[entry.normative_family] ?? entry.normative_family}</Text>
                  </td>
                  <td className={styles.normsTableTd}><div className={styles.statusStack}><Badge appearance="tint" color={st.color}>{st.label}</Badge>{entry.text_available && <Badge appearance="outline" color={q.color}>{q.label}</Badge>}</div></td>
                  <td className={styles.normsTableTd}>{entry.article_count || '—'}</td>
                  <td className={styles.normsTableTd}>{entry.canonical_source ? <Button as="a" href={entry.canonical_source} target="_blank" rel="noopener noreferrer" appearance="secondary" size="small">Abrir fuente</Button> : <Text className={styles.muted} size={200}>No disponible</Text>}</td>
                </tr>
              )
            })}
            {norms.length === 0 && (
              <tr><td className={styles.normsTableTd} colSpan={6}><Text className={styles.muted}>No hay normas. Importe una desde la URL oficial.</Text></td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={importOpen} onOpenChange={(_, data) => { if (!busy) setImportOpen(data.open) }}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Agregar normativa departamental</DialogTitle>
            <DialogContent>
              <form className={styles.importDialogForm} onSubmit={submitImport}>
                <div className={styles.importDialogIntro}><div className={styles.placeholderIcon}><AppIcon name="download" size={21} /></div><Text className={styles.muted}>Ingrese el enlace oficial. El sistema detectará el documento disponible y preparará su contenido para consulta.</Text></div>
                {importError && <MessageBar intent="error"><MessageBarBody>{importError}</MessageBarBody></MessageBar>}
                <Field label="Enlace oficial" hint="Se admiten fuentes de gub.uy, Junta Departamental, IMPO, MVOT y lavalleja.gub.uy." required>
                  <Input autoFocus placeholder="https://www.gub.uy/intendencia-lavalleja/…" value={importUrl} onChange={(_, data) => { setImportUrl(data.value); setImportError('') }} required />
                </Field>
                {busy && <div className={styles.importProgress}><Spinner size="tiny" /><div><Text weight="semibold" block>Procesando documento</Text><Text className={styles.muted} size={200}>Se está validando y preparando la fuente.</Text></div></div>}
                <DialogActions>
                  <Button appearance="secondary" type="button" disabled={busy} onClick={() => setImportOpen(false)}>Cancelar</Button>
                  <Button appearance="primary" type="submit" disabled={busy || !importUrl.trim()}>{busy ? 'Procesando…' : 'Agregar normativa'}</Button>
                </DialogActions>
              </form>
            </DialogContent>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
