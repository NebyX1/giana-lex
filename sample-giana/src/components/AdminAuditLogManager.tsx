import { useEffect, useState } from 'react'
import { Badge, MessageBar, MessageBarBody, Spinner, Text } from '@fluentui/react-components'
import { apiRequest } from '../api/client'
import { useAppStyles } from '../styles'
import { ManagerHeader } from './ManagerHeader'

type AuditEvent = {
  id: number
  event: string
  status: string
  subject_id?: string
  details: { title?: string }
  ip_address?: string
  created_at: string
  user?: { id: number; display_name?: string; email?: string }
}

const actionLabels: Record<string, string> = {
  'session.archive': 'Archivó una conversación',
  'session.restore': 'Restauró una conversación',
  'session.delete': 'Eliminó una conversación',
}

export function AdminAuditLogManager({ onClose }: { onClose: () => void }) {
  const styles = useAppStyles()
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    void apiRequest<{ events: AuditEvent[] }>('/api/admin/audit-events?limit=200')
      .then((response) => setEvents(response.events))
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : 'No se pudo cargar el registro de actividad.'))
      .finally(() => setLoading(false))
  }, [])

  return <section className={styles.normsManager} aria-label="Registro administrativo">
    <ManagerHeader eyebrow="ADMINISTRACIÓN" title="Registro de actividad" description="Trazabilidad de acciones sensibles realizadas dentro del sistema." onBack={onClose} />
    {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
    {loading ? <Spinner label="Cargando actividad" /> : <div className={styles.normsTableWrap}>
      <table className={styles.normsTable}>
        <thead><tr>
          <th className={styles.normsTableTh}>Fecha y hora</th>
          <th className={styles.normsTableTh}>Usuario</th>
          <th className={styles.normsTableTh}>Acción</th>
          <th className={styles.normsTableTh}>Objeto</th>
          <th className={styles.normsTableTh}>Estado</th>
          <th className={styles.normsTableTh}>Origen</th>
        </tr></thead>
        <tbody>
          {events.map((event) => <tr className={styles.normsTableRow} key={event.id}>
            <td className={styles.normsTableTd}>{new Date(event.created_at).toLocaleString()}</td>
            <td className={styles.normsTableTd}><Text weight="semibold" block>{event.user?.display_name ?? `Usuario #${event.user?.id ?? 'sistema'}`}</Text><Text className={styles.muted} size={200}>{event.user?.email ?? '—'}</Text></td>
            <td className={styles.normsTableTd}>{actionLabels[event.event] ?? event.event}</td>
            <td className={styles.normsTableTd}><Text weight="semibold" block>{event.details?.title ?? '—'}</Text>{event.subject_id && <Text className={styles.muted} size={200}>ID {event.subject_id}</Text>}</td>
            <td className={styles.normsTableTd}><Badge appearance="tint" color={event.status === 'completed' ? 'success' : event.status === 'denied' ? 'danger' : 'informative'}>{event.status}</Badge></td>
            <td className={styles.normsTableTd}>{event.ip_address ?? '—'}</td>
          </tr>)}
          {events.length === 0 && <tr><td className={styles.normsTableTd} colSpan={6}><Text className={styles.muted}>Todavía no hay actividad registrada.</Text></td></tr>}
        </tbody>
      </table>
    </div>}
  </section>
}
