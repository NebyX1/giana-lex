import { useState, type FormEvent } from 'react'
import {
  Button,
  Card,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Select,
  Text,
} from '@fluentui/react-components'
import { apiRequest } from '../api/client'
import type { Provider } from '../types'
import { useAppStyles } from '../styles'
import { ManagerHeader } from './ManagerHeader'

type Props = { providers: Provider[]; onChanged: () => Promise<void>; onClose?: () => void }

const providerName = (provider: Provider) => provider.provider === 'ollama' && provider.default_model?.includes('cloud')
  ? 'Ollama Cloud'
  : provider.display_name

const defaults = {
  featherless: 'https://api.featherless.ai/v1',
  ollama: 'http://localhost:11434/v1',
  custom: '',
}

export function ProviderManager({ providers, onChanged, onClose }: Props) {
  const styles = useAppStyles()
  const [kind, setKind] = useState<keyof typeof defaults>('featherless')
  const [name, setName] = useState('Featherless')
  const [baseUrl, setBaseUrl] = useState(defaults.featherless)
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function connectOpenAi() {
    setBusy(true)
    setError('')
    try {
      const response = await apiRequest<{ authorize_url: string }>('/api/providers/openai/authorize', { method: 'POST' })
      window.open(response.authorize_url, '_blank', 'noopener,noreferrer')
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo iniciar la conexión.')
    } finally { setBusy(false) }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await apiRequest('/api/providers', {
        method: 'POST',
        body: JSON.stringify({ provider: kind, display_name: name, base_url: baseUrl, default_model: model, api_key: apiKey }),
      })
      setApiKey('')
      await onChanged()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'No se pudo guardar el proveedor.')
    } finally { setBusy(false) }
  }

  async function remove(id: number) {
    setError('')
    try {
      await apiRequest(`/api/providers/${id}`, { method: 'DELETE' })
      await onChanged()
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'No se pudo eliminar.') }
  }

  return (
    <section className={styles.manager} aria-label="Proveedores de IA">
      <ManagerHeader eyebrow="CONFIGURACIÓN" title="Proveedores de inteligencia artificial" description="Conexiones y modelos disponibles para las consultas jurídicas." onBack={onClose} />
      {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
      <Card className={styles.openAiCard}>
        <div><Text weight="semibold" size={400}>Cuenta de OpenAI</Text><Text className={styles.muted} block>Conecte su cuenta mediante una autorización segura. Las credenciales permanecen cifradas en el servidor.</Text></div>
        <Button appearance="primary" disabled={busy} onClick={connectOpenAi}>Conectar OpenAI</Button>
      </Card>
      <form className={styles.providerForm} onSubmit={submit}>
        <Field label="Tipo">
          <Select value={kind} onChange={(_, data) => {
            const value = data.value as keyof typeof defaults
            setKind(value); setBaseUrl(defaults[value]); setName(value === 'ollama' ? 'Ollama Cloud' : value === 'custom' ? 'Proveedor cloud personalizado' : 'Featherless')
          }}>
            <option value="featherless">Featherless</option><option value="ollama">Ollama Cloud (pasarela)</option><option value="custom">API cloud compatible con OpenAI</option>
          </Select>
        </Field>
        <Field label="Nombre" required><Input value={name} onChange={(_, data) => setName(data.value)} required /></Field>
        <Field label="URL base" required><Input value={baseUrl} onChange={(_, data) => setBaseUrl(data.value)} required /></Field>
        <Field label="Modelo predeterminado"><Input value={model} onChange={(_, data) => setModel(data.value)} placeholder="Identificador del modelo cloud" /></Field>
        {kind !== 'ollama' && <Field label="Clave API" required><Input type="password" autoComplete="off" value={apiKey} onChange={(_, data) => setApiKey(data.value)} required /></Field>}
        <Button appearance="primary" type="submit" disabled={busy}>Guardar conexión</Button>
      </form>
      <div className={styles.connectionList}>
        <Text weight="semibold">Conexiones guardadas</Text>
        {providers.length === 0 && <Text className={styles.muted}>Todavía no hay conexiones.</Text>}
        {providers.map((provider) => <Card key={provider.id} className={styles.connectionCard}>
          <div><Text weight="semibold">{providerName(provider)}</Text><Text className={styles.muted} block>{provider.provider === 'ollama' ? 'Pasarela cloud' : provider.provider} · {provider.default_model || 'Modelo por sesión'}</Text></div>
          <Button appearance="subtle" onClick={() => void remove(provider.id)}>Eliminar</Button>
        </Card>)}
      </div>
    </section>
  )
}
