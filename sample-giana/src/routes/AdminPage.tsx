import { useState } from 'react'
import { Button, Card, Text, Title1 } from '@fluentui/react-components'
import { Link } from 'react-router-dom'
import { AdminAuditLogManager } from '../components/AdminAuditLogManager'
import { AdminUsersManager } from '../components/AdminUsersManager'
import { AppIcon } from '../components/AppIcon'
import type { User } from '../types'

export function AdminPage({ user }: { user: User }) {
  const [view, setView] = useState<'home' | 'users' | 'audit'>('home')
  if (!user.is_superuser) return <main className="legal-page"><Title1 as="h1">Acceso restringido</Title1><Text>Esta sección requiere permisos administrativos.</Text><Link to="/cases">Volver a expedientes</Link></main>
  if (view === 'users') return <AdminUsersManager onClose={() => setView('home')} />
  if (view === 'audit') return <AdminAuditLogManager onClose={() => setView('home')} />
  return <main className="legal-page admin-page"><Link className="legal-back" to="/cases"><AppIcon name="arrow-left" /> Volver</Link><Title1 as="h1">Administración</Title1><div className="admin-grid"><Card><AppIcon name="users" size={28} /><Text size={500} weight="semibold">Usuarios y permisos</Text><Button onClick={() => setView('users')}>Administrar</Button></Card><Card><AppIcon name="history" size={28} /><Text size={500} weight="semibold">Registro de actividad</Text><Button onClick={() => setView('audit')}>Consultar</Button></Card></div></main>
}
