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
  Spinner,
  Switch,
  Text,
} from '@fluentui/react-components'
import { apiRequest } from '../api/client'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'
import { ManagerHeader } from './ManagerHeader'

type NormEntry = {
  id: string
  tipo: string
  numero: string
  anio: number | string
  title: string
  nombre: string
  canonical_url: string
  active: boolean
  index_status: string
  article_count: number
  chunk_count: number
  last_synced_at: string | null
  last_error: string | null
  checksum: string
}

type Stats = {
  total: number
  active: number
  inactive: number
  indexed: number
  articles: number
  chunks: number
  missing_index: number
}

type ImportResult = {
  status: string
  norma_id: string | null
  message: string
  article_count: number
  chunk_count: number
  existing: boolean
  changed: boolean
}

type Props = { onClose: () => void }

const statusLabel = (entry: NormEntry): { label: string; color: 'success' | 'informative' | 'severe' | 'warning' } => {
  if (entry.last_error && entry.index_status !== 'indexed') return { label: 'Error', color: 'severe' }
  if (!entry.active) return { label: 'Desactivada', color: 'warning' }
  if (entry.index_status === 'indexed') return { label: 'Indexada', color: 'success' }
  if (entry.index_status === 'indexing') return { label: 'Indexando', color: 'informative' }
  return { label: 'Disponible', color: 'informative' }
}

export function NationalNormsManager({ onClose }: Props) {
  const styles = useAppStyles()
  const [norms, setNorms] = useState<NormEntry[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [query, setQuery] = useState('')
  const [importUrl, setImportUrl] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [importError, setImportError] = useState('')
  const [busy, setBusy] = useState(false)
  const [toggling, setToggling] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState<string | null>(null)
  const [repairing, setRepairing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async (search?: string) => {
    setError('')
    try {
      const params = search ? `?q=${encodeURIComponent(search)}` : ''
      const response = await apiRequest<{ norms: NormEntry[]; stats: Stats }>(`/api/config/normativa/nacional${params}`)
      setNorms(response.norms)
      setStats(response.stats)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cargar la normativa.')
    }
  }, [])

  useEffect(() => {
    const handle = setTimeout(() => { void load(query) }, query ? 300 : 0)
    return () => clearTimeout(handle)
  }, [load, query])

  function normalizedImportUrl() {
    const raw = importUrl.trim()
    const candidate = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`
    let parsed: URL
    try { parsed = new URL(candidate) } catch { throw new Error('Ingrese una URL válida de IMPO.') }
    if (!['impo.com.uy', 'www.impo.com.uy'].includes(parsed.hostname.toLowerCase())) throw new Error('La dirección debe pertenecer a impo.com.uy.')
    const parts = parsed.pathname.split('/').filter(Boolean)
    if (parts[0]?.toLowerCase() !== 'bases' || parts.length < 3) throw new Error('Use el enlace completo de la norma, por ejemplo /bases/leyes/18381-2008.')
    return parsed.toString()
  }

  async function submitImport(event: FormEvent) {
    event.preventDefault()
    if (!importUrl.trim() || busy) return
    setBusy(true); setError(''); setImportError(''); setNotice('')
    try {
      const normalizedUrl = normalizedImportUrl()
      const response = await apiRequest<{ result: ImportResult }>('/api/config/normativa/nacional/import', {
        method: 'POST', body: JSON.stringify({ url: normalizedUrl }),
      })
      const details = response.result.article_count ? ` ${response.result.article_count} artículos quedaron disponibles.` : ''
      setNotice(`${response.result.message}${details}`)
      setImportUrl('')
      setImportOpen(false)
      await load(query)
    } catch (caught) {
      setImportError(caught instanceof Error ? caught.message : 'No se pudo importar la norma.')
    } finally { setBusy(false) }
  }

  async function toggleActive(entry: NormEntry) {
    setToggling(entry.id); setError(''); setNotice('')
    try {
      const endpoint = entry.active ? 'deactivate' : 'activate'
      await apiRequest<{ result: ImportResult }>(`/api/config/normativa/nacional/${entry.id}/${endpoint}`, { method: 'POST' })
      setNorms((items) => items.map((item) => item.id === entry.id ? { ...item, active: !entry.active } : item))
      await load(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cambiar el estado.')
    } finally { setToggling(null) }
  }

  async function refresh(entry: NormEntry) {
    setRefreshing(entry.id); setError(''); setNotice('')
    try {
      const response = await apiRequest<{ result: ImportResult }>(`/api/config/normativa/nacional/${entry.id}/refresh`, { method: 'POST' })
      setNotice(response.result.message)
      await load(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo actualizar la norma.')
    } finally { setRefreshing(null) }
  }

  async function repairIndex() {
    setRepairing(true); setError(''); setNotice('')
    try {
      const response = await apiRequest<{ result: { repaired: number; failed: number; available_sources: number } }>('/api/config/normativa/nacional/repair-index', { method: 'POST' })
      setNotice(`Índice reparado: ${response.result.repaired} normas recuperadas, ${response.result.available_sources} disponibles para consulta${response.result.failed ? ` y ${response.result.failed} con error` : ''}.`)
      await load(query)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo reparar el índice jurídico.')
    } finally { setRepairing(false) }
  }

  return (
    <section className={styles.normsManager} aria-label="Normativa nacional">
      <ManagerHeader eyebrow="BIBLIOTECA JURÍDICA" title="Normativa nacional" description="Normas oficiales disponibles para investigación y fundamentación." onBack={onClose} actions={<Button appearance="primary" icon={<AppIcon name="download" />} onClick={() => { setImportError(''); setImportOpen(true) }}>Importar desde IMPO</Button>} />

      {stats && (
        <div className={styles.statsRow}>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="book" /></div><div><Text size={200} className={styles.muted}>Normas disponibles</Text><Text size={600} weight="semibold" block>{stats.total}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="shield" /></div><div><Text size={200} className={styles.muted}>Activas para consulta</Text><Text size={600} weight="semibold" block>{stats.active}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="document" /></div><div><Text size={200} className={styles.muted}>Artículos procesados</Text><Text size={600} weight="semibold" block>{stats.articles}</Text></div></Card>
          <Card className={styles.statCard}><div className={styles.statIcon}><AppIcon name="sources" /></div><div><Text size={200} className={styles.muted}>Indexadas</Text><Text size={600} weight="semibold" block>{stats.indexed}</Text></div></Card>
        </div>
      )}

      {stats && stats.missing_index > 0 && (
        <MessageBar intent="warning">
          <MessageBarBody>
            {stats.missing_index} normas tienen copia local pero no están disponibles en el buscador.
            {' '}<Button appearance="primary" size="small" disabled={repairing} onClick={() => void repairIndex()}>{repairing ? <Spinner size="tiny" /> : 'Reparar índice'}</Button>
          </MessageBarBody>
        </MessageBar>
      )}

      <div className={styles.managementToolbar}>
        <Input className={styles.searchField} contentBefore={<AppIcon name="search" size={16} />} placeholder="Buscar por nombre, número, tipo o año…" value={query} onChange={(_, data) => setQuery(data.value)} />
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
              <th className={styles.normsTableTh}>Título</th>
              <th className={styles.normsTableTh}>Estado</th>
              <th className={styles.normsTableTh}>Artículos</th>
              <th className={styles.normsTableTh}>Actualización</th>
              <th className={styles.normsTableTh}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {norms.map((entry) => {
              const status = statusLabel(entry)
              return (
                <tr className={styles.normsTableRow} key={entry.id}>
                  <td className={styles.normsTableTd}>
                    <Switch checked={entry.active} disabled={toggling === entry.id} onChange={() => void toggleActive(entry)} aria-label={`Activar ${entry.title}`} />
                  </td>
                  <td className={styles.normsTableTd}><div className={styles.normIdentity}><Text weight="semibold">{entry.tipo} {entry.numero}</Text><Text className={styles.muted} size={200}>{entry.anio}</Text></div></td>
                  <td className={`${styles.normsTableTd} ${styles.normTitleCell}`} title={entry.title}><Text weight="semibold">{entry.title}</Text></td>
                  <td className={styles.normsTableTd}><Badge appearance="tint" color={status.color}>{status.label}</Badge></td>
                  <td className={styles.normsTableTd}>{entry.article_count}</td>
                  <td className={styles.normsTableTd}>{entry.last_synced_at ? new Date(entry.last_synced_at).toLocaleDateString() : '—'}</td>
                  <td className={styles.normsTableTd}>
                    <span className={styles.badgeGap}>
                      <Button as="a" href={entry.canonical_url} target="_blank" rel="noopener noreferrer" appearance="secondary" size="small">Abrir en IMPO</Button>
                      <Button appearance="subtle" size="small" disabled={refreshing === entry.id} onClick={() => void refresh(entry)}>
                        {refreshing === entry.id ? <Spinner size="tiny" /> : 'Actualizar'}
                      </Button>
                    </span>
                  </td>
                </tr>
              )
            })}
            {norms.length === 0 && (
              <tr><td className={styles.normsTableTd} colSpan={7}><Text className={styles.muted}>No hay normas disponibles. Importe una norma desde IMPO para comenzar.</Text></td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={importOpen} onOpenChange={(_, data) => { if (!busy) setImportOpen(data.open) }}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Importar normativa desde IMPO</DialogTitle>
            <DialogContent>
              <form className={styles.importDialogForm} onSubmit={submitImport}>
                <div className={styles.importDialogIntro}><div className={styles.placeholderIcon}><AppIcon name="download" size={21} /></div><Text className={styles.muted}>Pegue el enlace público de una ley, decreto, código o artículo. Giana descargará la norma completa y preparará su contenido para búsquedas.</Text></div>
                {importError && <MessageBar intent="error"><MessageBarBody>{importError}</MessageBarBody></MessageBar>}
                <Field label="Enlace de IMPO" hint="También puede pegar el enlace de un artículo individual." required>
                  <Input autoFocus placeholder="https://www.impo.com.uy/bases/leyes/18381-2008" value={importUrl} onChange={(_, data) => { setImportUrl(data.value); setImportError('') }} required />
                </Field>
                {busy && <div className={styles.importProgress}><Spinner size="tiny" /><div><Text weight="semibold" block>Descargando e indexando</Text><Text className={styles.muted} size={200}>La operación puede demorar unos momentos.</Text></div></div>}
                <DialogActions>
                  <Button appearance="secondary" type="button" disabled={busy} onClick={() => setImportOpen(false)}>Cancelar</Button>
                  <Button appearance="primary" type="submit" disabled={busy || !importUrl.trim()}>{busy ? 'Procesando…' : 'Importar normativa'}</Button>
                </DialogActions>
              </form>
            </DialogContent>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
