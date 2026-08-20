import { useEffect, useState } from 'react'
import { Avatar, Button, FluentProvider, MessageBar, MessageBarBody, Spinner, Text, webDarkTheme, webLightTheme } from '@fluentui/react-components'
import { AddRegular, ChatRegular, DocumentRegular, NavigationRegular, PanelRightRegular, SettingsRegular, SignOutRegular, WeatherMoonRegular, WeatherSunnyRegular } from '@fluentui/react-icons'
import { api, authApi } from './api.js'
import AuthScreen from './components/AuthScreen.jsx'
import CasesView from './components/CasesView.jsx'
import ChatPane from './components/ChatPane.jsx'
import DebugPanel from './components/DebugPanel.jsx'
import DynamicForm from './components/DynamicForm.jsx'
import { AuditManager, NormsManager, ProviderManager, UsersManager } from './components/ManagementViews.jsx'
import RightPanel from './components/RightPanel.jsx'
import SettingsCenter from './components/SettingsCenter.jsx'
import KnowledgeCenter from './components/knowledge/KnowledgeCenter.jsx'
import SkillPicker from './components/SkillPicker.jsx'
import SkillResult from './components/SkillResult.jsx'

export default function App() {
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('giana-lex-theme') === 'dark' || (!localStorage.getItem('giana-lex-theme') && window.matchMedia?.('(prefers-color-scheme: dark)').matches))
  const [user, setUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [view, setView] = useState('chat')
  const [query, setQuery] = useState('')
  const [conversation, setConversation] = useState(null)
  const [recentConversations, setRecentConversations] = useState([])
  const [recentLoading, setRecentLoading] = useState(false)
  const [recentError, setRecentError] = useState('')
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [rightOpen, setRightOpen] = useState(true)

  useEffect(() => {
    localStorage.setItem('giana-lex-theme', darkMode ? 'dark' : 'light')
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light'
  }, [darkMode])

  useEffect(() => {
    void authApi.me().then((response) => setUser(response.user)).catch(() => setUser(null)).finally(() => setAuthLoading(false))
  }, [])

  const loadRecentConversations = async () => {
    if (!user) return
    setRecentLoading(true)
    setRecentError('')
    try {
      const response = await api.list()
      setRecentConversations(response.conversations)
    } catch (exception) {
      setRecentConversations([])
      setRecentError(exception.message)
    } finally {
      setRecentLoading(false)
    }
  }

  useEffect(() => {
    if (!user) {
      setRecentConversations([])
      return
    }
    void loadRecentConversations()
  }, [user, view])

  const authenticate = (nextUser) => setUser(nextUser)
  const logout = async () => {
    try { await authApi.logout() } finally {
      setUser(null); setView('chat'); setConversation(null); setMessages([]); setRecentConversations([]); setRecentError(''); setQuery(''); setError('')
    }
  }
  const navigate = (nextView) => { setView(nextView); setSidebarOpen(false) }
  const resetConversation = () => { setConversation(null); setMessages([]); setQuery(''); setError(''); setView('chat'); setSidebarOpen(false); setRightOpen(true) }

  const perform = async (key, action, userText) => {
    setBusy(key)
    setError('')
    if (userText) setMessages((current) => [...current, { role: 'user', text: userText }])
    try {
      const data = await action()
      setConversation(data)
      void loadRecentConversations()
      if (data.message) setMessages((current) => [...current, { role: 'assistant', text: data.message }])
      if (data.draft) setRightOpen(true)
      return data
    } catch (exception) {
      setError(exception.message)
      if (userText) setMessages((current) => current.slice(0, -1))
      throw exception
    } finally {
      setBusy(null)
    }
  }

  const send = async () => {
    const message = query.trim()
    if (!message) return
    setQuery('')
    try { await perform('create', () => api.create(message), message) } catch { setQuery(message) }
  }
  const submitForm = (answers) => perform('form', () => api.form(conversation.conversation_id, answers)).catch(() => null)
  const revise = (instructions) => perform('revise', () => api.revise(conversation.conversation_id, instructions), instructions)
  const approve = () => perform('approve', () => api.approve(conversation.conversation_id)).catch(() => null)
  const runSkill = (key, answers) => perform(`skill-${key}`, () => api.skill(conversation.conversation_id, key, answers)).catch(() => null)
  const openConversation = async (conversationId) => {
    setBusy('load-conversation')
    setError('')
    try {
      const data = await api.get(conversationId)
      setConversation(data)
      const restoredMessages = [{ role: 'user', text: recentConversations.find((item) => item.conversation_id === conversationId)?.title || 'Consulta jurídica' }]
      if (data.message) restoredMessages.push({ role: 'assistant', text: data.message })
      setMessages(restoredMessages)
      setView('chat')
      setSidebarOpen(false)
      setRightOpen(Boolean(data.draft))
    } catch (exception) {
      setError(exception.message)
    } finally {
      setBusy(null)
    }
  }

  const theme = darkMode ? webDarkTheme : webLightTheme
  if (authLoading) return <FluentProvider theme={theme}><main className="auth-page"><Spinner label="Conectando con Giana-Lex" /></main></FluentProvider>
  if (!user) return <FluentProvider theme={theme}><AuthScreen darkMode={darkMode} onToggleTheme={() => setDarkMode((value) => !value)} onAuthenticated={authenticate} /></FluentProvider>

  let content
  if (view === 'settings') content = <SettingsCenter hasConversation={Boolean(conversation)} skills={conversation?.skills || []} onNavigate={navigate} onClose={() => navigate('chat')} />
  if (view === 'knowledge') content = <KnowledgeCenter onClose={() => navigate('settings')} />
  if (view === 'national') content = <NormsManager kind="national" onClose={() => navigate('settings')} />
  if (view === 'departmental') content = <NormsManager kind="departmental" onClose={() => navigate('settings')} />
  if (view === 'providers') content = <ProviderManager onClose={() => navigate('settings')} />
  if (view === 'users') content = <UsersManager onClose={() => navigate('settings')} />
  if (view === 'audit') content = <AuditManager onClose={() => navigate('settings')} />
  if (view === 'cases') content = <CasesView onClose={() => navigate('chat')} />

  return <FluentProvider theme={theme} className="app-provider">
    {content || <div className={`application-shell ${rightOpen ? 'right-open' : 'panel-closed'} ${sidebarOpen ? 'sidebar-open' : ''}`}>
      {sidebarOpen && <button className="sidebar-scrim" aria-label="Cerrar navegación" onClick={() => setSidebarOpen(false)} />}
      <aside className="sidebar">
        <div className="sidebar-header"><div className="sidebar-brand">GL</div><div><Text weight="semibold" block>Giana-Lex</Text><Text size={100} className="muted">Inteligencia jurídica</Text></div></div>
        <div className="sidebar-actions"><Button className="new-conversation" appearance="primary" icon={<AddRegular />} onClick={resetConversation}>Nueva consulta</Button><span className="nav-label">ESPACIO DE TRABAJO</span><Button appearance="subtle" icon={<ChatRegular />} data-active={view === 'chat'} onClick={() => { navigate('chat'); void loadRecentConversations() }}>Conversación general</Button><Button appearance="subtle" icon={<DocumentRegular />} onClick={() => navigate('cases')}>Expedientes</Button></div>
        <div className="session-list"><span className="nav-label">CONVERSACIONES RECIENTES</span>{recentConversations.length ? recentConversations.map((item) => <button key={item.conversation_id} className="session-row" data-active={conversation?.conversation_id === item.conversation_id} onClick={() => void openConversation(item.conversation_id)}><ChatRegular /><span>{item.title || 'Consulta jurídica'}</span></button>) : <Text className="empty-sessions" size={200}>{recentLoading ? 'Cargando conversaciones...' : recentError || 'Las consultas activas aparecerán aquí.'}</Text>}</div>
        <div className="sidebar-footer"><div className="sidebar-utilities"><Button appearance="subtle" icon={<SettingsRegular />} onClick={() => navigate('settings')}>Configurar</Button><Button appearance="subtle" icon={darkMode ? <WeatherSunnyRegular /> : <WeatherMoonRegular />} onClick={() => setDarkMode((value) => !value)}>{darkMode ? 'Modo claro' : 'Nocturno'}</Button></div><div className="user-row"><Avatar name={user.display_name} color="colorful" /><div><Text weight="semibold" size={200} block>{user.display_name}</Text><Text className="muted" size={100} block>{user.email}</Text></div><Button appearance="subtle" icon={<SignOutRegular />} aria-label="Cerrar sesión" onClick={() => void logout()} /></div></div>
      </aside>
      <main className="chat-workspace">
        <header className="topbar"><Button className="mobile-menu" appearance="subtle" icon={<NavigationRegular />} aria-label="Abrir navegación" onClick={() => setSidebarOpen(true)} /><div className="topbar-title"><Text weight="semibold" size={400} block>{conversation ? `EXP. ${conversation.conversation_id.slice(0, 8).toUpperCase()}` : 'Nueva consulta jurídica'}</Text><div className="workspace-status"><span data-busy={Boolean(busy)} />{busy ? 'Procesando solicitud' : conversation ? 'Workflow sincronizado' : 'Listo para comenzar'}</div></div><Button appearance="subtle" icon={<PanelRightRegular />} onClick={() => setRightOpen((value) => !value)}>{rightOpen ? 'Ocultar panel' : 'Panel de trabajo'}</Button></header>
        {error && <MessageBar className="global-error" intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
        <ChatPane messages={messages} hasConversation={Boolean(conversation)} value={query} onChange={setQuery} onSend={send} busy={busy}>
          {conversation?.form && conversation.stage === 'collecting_info' && <DynamicForm form={conversation.form} onSubmit={submitForm} busy={busy === 'form'} />}
          {conversation?.approved && <><SkillPicker skills={conversation.skills} onRun={(key) => runSkill(key)} onExport={() => { window.location.href = api.exportUrl(conversation.conversation_id) }} busy={busy} />{Object.entries(conversation.skill_results).map(([key, result]) => <SkillResult key={key} skill={conversation.skills.find((skill) => skill.key === key)} result={result} onSubmit={(answers) => runSkill(key, answers)} busy={busy === `skill-${key}`} />)}</>}
          <DebugPanel debug={conversation?.debug} />
        </ChatPane>
      </main>
      {rightOpen && <RightPanel conversation={conversation} busy={busy} onRevise={revise} onApprove={approve} onClose={() => setRightOpen(false)} />}
    </div>}
  </FluentProvider>
}
