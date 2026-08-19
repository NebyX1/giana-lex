import { Button, Textarea } from '@fluentui/react-components'
import { SendRegular } from '@fluentui/react-icons'

export default function ChatPane({ messages, value, onChange, onSend, busy, children }) {
  return (
    <section className="chat-pane" aria-label="Interaccion">
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <span className="eyebrow">LABORATORIO DE REDACCION</span>
            <h2>¿Que resolucion necesitás preparar?</h2>
            <p>Describí el objetivo. Giana buscará antecedentes y te pedirá únicamente la información necesaria.</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
            <span>{message.role === 'user' ? 'Vos' : 'Giana'}</span>
            <p>{message.text}</p>
          </div>
        ))}
        {busy === 'create' && <p className="activity">Buscando antecedentes y generando formulario...</p>}
      </div>
      {children}
      {!messages.length && (
        <div className="composer">
          <Textarea
            resize="vertical"
            size="large"
            value={value}
            onChange={(_, data) => onChange(data.value)}
            placeholder="Necesito que me ayudes a crear una resolución..."
            aria-label="Solicitud"
          />
          <Button appearance="primary" icon={<SendRegular />} disabled={!value.trim() || busy === 'create'} onClick={onSend}>
            {busy === 'create' ? 'Analizando...' : 'Enviar'}
          </Button>
        </div>
      )}
    </section>
  )
}
