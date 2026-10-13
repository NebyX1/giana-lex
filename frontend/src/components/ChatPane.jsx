import { Button, Spinner, Text, Textarea } from '@fluentui/react-components'
import { ArrowRightRegular, DocumentTextRegular, SearchRegular, SendRegular, ShieldCheckmarkRegular, SparkleRegular } from '@fluentui/react-icons'
import DynamicForm from './DynamicForm.jsx'

const prompts = [
  { icon: DocumentTextRegular, label: 'REDACCIÓN', text: 'Preparar una resolución administrativa a partir de antecedentes.' },
  { icon: ShieldCheckmarkRegular, label: 'CONTROL', text: 'Revisar los riesgos jurídicos de un acto administrativo.' },
  { icon: SearchRegular, label: 'INVESTIGACIÓN', text: 'Localizar normativa aplicable a una situación concreta.' },
  { icon: SparkleRegular, label: 'SÍNTESIS', text: 'Resumir antecedentes para fundamentar una decisión.' },
]

export default function ChatPane({ messages, hasConversation, value, onChange, onSend, busy, children }) {
  return (
    <section className="chat-pane" aria-label="Interacción">
      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome">
            <div className="welcome-icon"><SparkleRegular /></div>
            <Text size={700} weight="semibold" block>¿Qué necesita resolver?</Text>
            <Text className="welcome-summary" size={400}>Describa el objetivo jurídico. Giana buscará antecedentes y solicitará únicamente la información necesaria.</Text>
            <div className="prompt-grid">{prompts.map(({ icon: Icon, label, text }) => <button className="prompt-card" type="button" key={label} onClick={() => onChange(text)}><span className="prompt-label">{label}</span><div><Text weight="semibold">{text}</Text><Icon /></div></button>)}</div>
          </div>
        )}
        {messages.map((message, index) => message.role === 'form' ? (
          <DynamicForm key={message.id || `form-${index}`} form={message.form} initialValues={message.answers} disabled onSubmit={() => {}} />
        ) : (
          <div className={`message-row ${message.role}`} key={`${message.role}-${index}`}>
            {message.role === 'assistant' && <div className="agent-avatar">GL</div>}
            <div className="message-content"><span>{message.role === 'user' ? 'USTED' : 'GIANA-LEX'}</span><p className={`bubble ${message.role}`}>{message.text}</p></div>
          </div>
        ))}
        {busy === 'create' && <div className="activity"><Spinner size="tiny" /><span>Preparando la respuesta…</span></div>}
        {children}
      </div>
      {!hasConversation && (
        <div className="composer-wrap"><div className="composer"><Textarea resize="none" size="large" value={value} onChange={(_, data) => onChange(data.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); onSend() } }} placeholder="Describa la consulta o el documento que necesita preparar…" aria-label="Solicitud" /><div className="composer-actions"><Text size={100} className="muted">Enter para enviar · Shift + Enter para nueva línea</Text><Button appearance="primary" icon={busy === 'create' ? undefined : <SendRegular />} disabled={!value.trim() || busy === 'create'} onClick={onSend}>{busy === 'create' ? <Spinner size="tiny" /> : <>Enviar consulta <ArrowRightRegular /></>}</Button></div></div></div>
      )}
    </section>
  )
}
