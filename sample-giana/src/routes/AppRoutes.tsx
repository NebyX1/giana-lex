import { BrowserRouter, HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ChatWorkspace } from '../components/ChatWorkspace'
import { CaseListPage } from '../features/cases/CaseListPage'
import { CaseWorkspace } from '../features/cases/CaseWorkspace'
import type { Provider, User } from '../types'
import { AdminPage } from './AdminPage'
import { StageLanding } from './StageLanding'

type Props = { user: User; providers: Provider[]; setProviders: (providers: Provider[]) => void; darkMode: boolean; onToggleTheme: () => void; onLogout: () => void }

export function AppRoutes(props: Props) {
  const Router = window.location.protocol === 'file:' ? HashRouter : BrowserRouter
  return <Router><Routes>
    <Route path="/" element={<ChatWorkspace {...props} />} />
    <Route path="/cases" element={<CaseListPage />} />
    <Route path="/cases/:caseId" element={<CaseWorkspace />} />
    <Route path="/cases/:caseId/intake" element={<CaseWorkspace />} />
    <Route path="/cases/:caseId/research" element={<CaseWorkspace />} />
    <Route path="/cases/:caseId/draft" element={<CaseWorkspace />} />
    <Route path="/cases/:caseId/review" element={<CaseWorkspace />} />
    <Route path="/intake" element={<StageLanding title="Datos del expediente" />} />
    <Route path="/research" element={<StageLanding title="Investigación jurídica" />} />
    <Route path="/draft" element={<StageLanding title="Borradores" />} />
    <Route path="/review" element={<StageLanding title="Revisión humana" />} />
    <Route path="/settings" element={<ChatWorkspace {...props} initialView="settings" />} />
    <Route path="/admin" element={<AdminPage user={props.user} />} />
    <Route path="*" element={<Navigate to="/cases" replace />} />
  </Routes></Router>
}
