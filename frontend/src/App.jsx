import { useState } from 'react'
import { MessageBar, MessageBarBody } from '@fluentui/react-components'
import { ShieldCheckmarkRegular } from '@fluentui/react-icons'
import { api } from './api.js'
import ChatPane from './components/ChatPane.jsx'
import DebugPanel from './components/DebugPanel.jsx'
import DraftPanel from './components/DraftPanel.jsx'
import DynamicForm from './components/DynamicForm.jsx'
import SkillPicker from './components/SkillPicker.jsx'
import SkillResult from './components/SkillResult.jsx'

export default function App() {
  const [query, setQuery] = useState('')
  const [conversation, setConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')

  const perform = async (key, action, userText) => {
    setBusy(key)
    setError('')
    if (userText) setMessages((current) => [...current, { role: 'user', text: userText }])
    try {
      const data = await action()
      setConversation(data)
      if (data.message) setMessages((current) => [...current, { role: 'assistant', text: data.message }])
      return data
    } catch (exception) {
      setError(exception.message)
      throw exception
    } finally {
      setBusy(null)
    }
  }

  const send = async () => {
    const message = query.trim()
    if (!message) return
    setQuery('')
    await perform('create', () => api.create(message), message).catch(() => {})
  }

  const submitForm = (answers) => perform('form', () => api.form(conversation.conversation_id, answers)).catch(() => {})
  const revise = (instructions) => perform('revise', () => api.revise(conversation.conversation_id, instructions), instructions).catch(() => {})
  const approve = () => perform('approve', () => api.approve(conversation.conversation_id)).catch(() => {})
  const runSkill = (key, answers) => perform(`skill-${key}`, () => api.skill(conversation.conversation_id, key, answers)).catch(() => {})

  const hasDraft = Boolean(conversation?.draft)

  return (
    <div className="app-shell">
      <header>
        <div className="brand-mark"><ShieldCheckmarkRegular /></div>
        <div><h1>Giana Lex</h1><p>Asistente experimental de redacción administrativa</p></div>
        {conversation && <span className="conversation-id">EXP. {conversation.conversation_id.slice(0, 8).toUpperCase()}</span>}
      </header>
      {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
      <main className={hasDraft ? 'workspace split' : 'workspace'}>
        <div>
          <ChatPane messages={messages} value={query} onChange={setQuery} onSend={send} busy={busy}>
            {conversation?.form && conversation.stage === 'collecting_info' && (
              <DynamicForm form={conversation.form} onSubmit={submitForm} busy={busy === 'form'} />
            )}
            {conversation?.approved && (
              <>
                <SkillPicker
                  skills={conversation.skills}
                  onRun={(key) => runSkill(key)}
                  onExport={() => { window.location.href = api.exportUrl(conversation.conversation_id) }}
                  busy={busy}
                />
                {Object.entries(conversation.skill_results).map(([key, result]) => (
                  <SkillResult
                    key={key}
                    skill={conversation.skills.find((skill) => skill.key === key)}
                    result={result}
                    onSubmit={(answers) => runSkill(key, answers)}
                    busy={busy === `skill-${key}`}
                  />
                ))}
              </>
            )}
          </ChatPane>
          <DebugPanel debug={conversation?.debug} />
        </div>
        {hasDraft && (
          <DraftPanel
            draft={conversation.draft}
            approved={conversation.approved}
            onRevise={revise}
            onApprove={approve}
            busy={busy}
          />
        )}
      </main>
    </div>
  )
}
