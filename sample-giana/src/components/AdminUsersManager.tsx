import { useEffect, useState, type FormEvent } from 'react'
import {
  Badge,
  Button,
  Dialog,
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

type AdminUser = {
  id: number
  email: string
  display_name: string
  is_active: boolean
  is_superuser: boolean
  created_at: string | null
  last_login_at: string | null
}

export function AdminUsersManager({ onClose }: { onClose: () => void }) {
  const styles = useAppStyles()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ email: '', display_name: '', password: '', is_superuser: false })

  async function load() {
    setError('')
    try {
      const response = await apiRequest<{ users: AdminUser[] }>('/api/admin/users')
      setUsers(response.users)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudieron cargar los usuarios.')
    }
  }

  useEffect(() => { void load() }, [])

  async function createUser(event: FormEvent) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setNotice('Usuario creado correctamente.')
      setCreateOpen(false)
      setForm({ email: '', display_name: '', password: '', is_superuser: false })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo crear el usuario.')
    } finally { setBusy(false) }
  }

  async function toggleActive(user: AdminUser) {
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest(`/api/admin/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !user.is_active }),
      })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cambiar el estado.')
    } finally { setBusy(false) }
  }

  async function toggleSuper(user: AdminUser) {
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest(`/api/admin/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_superuser: !user.is_superuser }),
      })
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo cambiar el rol.')
    } finally { setBusy(false) }
  }

  async function removeUser(user: AdminUser) {
    setBusy(true); setError(''); setNotice('')
    try {
      await apiRequest(`/api/admin/users/${user.id}`, { method: 'DELETE' })
      setNotice('Usuario eliminado.')
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo eliminar.')
    } finally { setBusy(false) }
  }

  return (
    <section className={styles.normsManager} aria-label="Gestión de usuarios">
      <ManagerHeader eyebrow="ADMINISTRACIÓN" title="Usuarios y permisos" description="Gestione el acceso, estado y rol de las personas habilitadas." onBack={onClose} actions={<Button appearance="primary" icon={<AppIcon name="plus" />} onClick={() => setCreateOpen(true)}>Crear usuario</Button>} />

      {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
      {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}

      <div className={styles.normsTableWrap}>
        <table className={styles.normsTable}>
          <thead>
            <tr>
              <th className={styles.normsTableTh}>Nombre</th>
              <th className={styles.normsTableTh}>Email</th>
              <th className={styles.normsTableTh}>Rol</th>
              <th className={styles.normsTableTh}>Activo</th>
              <th className={styles.normsTableTh}>Creado</th>
              <th className={styles.normsTableTh}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr className={styles.normsTableRow} key={user.id}>
                <td className={styles.normsTableTd}>{user.display_name}</td>
                <td className={styles.normsTableTd}>{user.email}</td>
                <td className={styles.normsTableTd}>
                  <Badge appearance="tint" color={user.is_superuser ? 'brand' : 'informative'}>{user.is_superuser ? 'Administrador' : 'Usuario'}</Badge>
                </td>
                <td className={styles.normsTableTd}>
                  <Switch checked={user.is_active} disabled={busy} onChange={() => void toggleActive(user)} aria-label={`Activar ${user.display_name}`} />
                </td>
                <td className={styles.normsTableTd}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</td>
                <td className={styles.normsTableTd}>
                  <span className={styles.badgeGap}>
                    <Button appearance="subtle" size="small" disabled={busy} onClick={() => void toggleSuper(user)}>{user.is_superuser ? 'Quitar admin' : 'Hacer admin'}</Button>
                    <Button appearance="subtle" size="small" disabled={busy} onClick={() => void removeUser(user)}>Eliminar</Button>
                  </span>
                </td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td className={styles.normsTableTd} colSpan={6}><Text className={styles.muted}>No hay usuarios.</Text></td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={createOpen} onOpenChange={(_, data) => setCreateOpen(data.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>Crear usuario</DialogTitle>
            <DialogContent>
              <form onSubmit={createUser} className={styles.formStack}>
                <Field label="Nombre" required><Input value={form.display_name} onChange={(_, data) => setForm({ ...form, display_name: data.value })} required /></Field>
                <Field label="Email" required><Input type="email" value={form.email} onChange={(_, data) => setForm({ ...form, email: data.value })} required /></Field>
                <Field label="Contraseña (mín. 12 caracteres)" required><Input type="password" value={form.password} onChange={(_, data) => setForm({ ...form, password: data.value })} required /></Field>
                <Field label="Super administrador">
                  <Switch checked={form.is_superuser} onChange={(_, data) => setForm({ ...form, is_superuser: data.checked })} />
                </Field>
                <Button appearance="primary" type="submit" disabled={busy}>{busy ? <Spinner size="tiny" /> : 'Crear'}</Button>
              </form>
            </DialogContent>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </section>
  )
}
