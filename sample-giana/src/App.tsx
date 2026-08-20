import { useEffect, useState } from 'react'
import { FluentProvider, Spinner, webDarkTheme, webLightTheme } from '@fluentui/react-components'
import { apiRequest, clearCsrfToken } from './api/client'
import { AuthScreen } from './components/AuthScreen'
import { AppRoutes } from './routes/AppRoutes'
import type { Provider, User } from './types'
import { useAppStyles } from './styles'

function App() {
  const styles = useAppStyles()
  const [darkMode, setDarkMode] = useState(() => {
    const saved = window.localStorage.getItem('giana-lex-theme')
    if (saved) return saved === 'dark'
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  })
  const [user, setUser] = useState<User | null>(null)
  const [providers, setProviders] = useState<Provider[]>([])
  const [loading, setLoading] = useState(true)
  const [connectionError, setConnectionError] = useState('')

  async function bootstrap(authenticatedUser?: User) {
    try {
      const currentUser = authenticatedUser ?? (await apiRequest<{ user: User }>('/api/auth/me')).user
      setUser(currentUser)
      const response = await apiRequest<{ providers: Provider[] }>('/api/providers')
      setProviders(response.providers)
      setConnectionError('')
    } catch (caught) {
      if (caught instanceof TypeError) setConnectionError('No se pudo conectar con el servidor de Giana-Lex.')
      if (!authenticatedUser) setUser(null)
    } finally { setLoading(false) }
  }

  useEffect(() => { void bootstrap() }, [])
  useEffect(() => {
    window.localStorage.setItem('giana-lex-theme', darkMode ? 'dark' : 'light')
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light'
  }, [darkMode])

  async function logout() {
    try { await apiRequest('/api/auth/logout', { method: 'POST' }) } finally {
      clearCsrfToken(); setUser(null); setProviders([])
    }
  }

  return (
    <FluentProvider theme={darkMode ? webDarkTheme : webLightTheme}>
      {loading ? <main className={styles.authPage}><Spinner label="Conectando con Giana-Lex" /></main> : user ? <AppRoutes user={user} providers={providers} setProviders={setProviders} darkMode={darkMode} onToggleTheme={() => setDarkMode((value) => !value)} onLogout={() => void logout()} /> : <AuthScreen darkMode={darkMode} onToggleTheme={() => setDarkMode((value) => !value)} offlineMessage={connectionError} onAuthenticated={(authenticated) => { setLoading(true); void bootstrap(authenticated) }} />}
    </FluentProvider>
  )
}

export default App
