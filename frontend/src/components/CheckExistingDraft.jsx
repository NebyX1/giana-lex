import { useState } from 'react'
import { Button, Card, Text, Title1 } from '@fluentui/react-components'
import { ArrowLeftRegular } from '@fluentui/react-icons'

export default function CheckExistingDraft({ onClose, onSubmit, busy }) {
  const [draft, setDraft] = useState('')
  const [context, setContext] = useState('')
  return <main className="standalone-page example-page">
    <header className="settings-hero"><Button icon={<ArrowLeftRegular />} onClick={onClose}>Volver</Button><div><Title1>Comprobar una resolución redactada</Title1><Text className="muted">Pegue el borrador. Gianna comparará referencias editoriales y verificará lo que puede confirmar con el texto disponible.</Text></div></header>
    <Card className="example-editor"><label>Objeto del caso o pregunta concreta<input value={context} onChange={(e) => setContext(e.target.value)} placeholder="Por ejemplo: rectificar una adjudicación" /></label><label>Borrador<textarea rows={22} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Pegue aquí el texto de la resolución" /></label><Button appearance="primary" disabled={Boolean(busy) || !draft.trim()} onClick={() => onSubmit(draft, context)}>{busy ? 'Comprobando...' : 'Comparar y comprobar'}</Button></Card>
  </main>
}
