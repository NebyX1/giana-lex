import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Button,
  Card,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Spinner,
  Text,
} from '@fluentui/react-components'
import { apiRequest } from '../api/client'
import type { User } from '../types'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'
import { authErrorMessage } from './authErrors'

type Props = { darkMode: boolean; onToggleTheme: () => void; onAuthenticated: (user: User) => void; offlineMessage?: string }

export function AuthScreen({ darkMode, onToggleTheme, onAuthenticated, offlineMessage }: Props) {
  const styles = useAppStyles()
  const [step, setStep] = useState<'login' | 'otp'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [captcha, setCaptcha] = useState('')
  const [captchaQuestion, setCaptchaQuestion] = useState('')
  const [captchaBusy, setCaptchaBusy] = useState(true)
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadCaptcha = useCallback(async (reportError = true) => {
    setCaptchaBusy(true)
    setCaptcha('')
    try {
      const response = await apiRequest<{ captcha: { question: string } }>('/api/auth/captcha')
      setCaptchaQuestion(response.captcha.question)
    } catch {
      setCaptchaQuestion('')
      if (reportError) setError('No se pudo cargar la verificación de seguridad.')
    } finally {
      setCaptchaBusy(false)
    }
  }, [])

  useEffect(() => { void loadCaptcha() }, [loadCaptcha])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (step === 'login') {
        await apiRequest('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email, password, captcha }),
        })
        setStep('otp')
      } else {
        const response = await apiRequest<{ user: User }>('/api/auth/verify', {
          method: 'POST',
          body: JSON.stringify({ code }),
        })
        onAuthenticated(response.user)
      }
    } catch (caught) {
      setError(authErrorMessage(caught, step))
      if (step === 'login') await loadCaptcha(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className={styles.authPage}>
      <section className={styles.authIntro}>
        <div className={styles.authGlow} aria-hidden="true" />
        <div className={styles.brandLockup}>
          <div className={styles.brandMark}>GL</div>
          <div>
            <Text className={styles.brandName} weight="semibold">GIANA-LEX</Text>
            <Text className={styles.brandDescriptor} block>Inteligencia jurídica</Text>
          </div>
        </div>
        <div className={styles.authPitch}>
          <div className={styles.authEyebrow}>PLATAFORMA DE TRABAJO JURÍDICO</div>
          <h1>Rigor jurídico, respaldado por evidencia.</h1>
          <Text className={styles.authSummary} size={400}>
            Investigue normativa, prepare documentos y revise expedientes con fuentes verificables y control profesional en cada etapa.
          </Text>
        </div>
        <div className={styles.trustList} aria-label="Capacidades de la plataforma">
          <span>Fuentes verificables</span>
          <span>Trazabilidad integral</span>
          <span>Revisión humana</span>
        </div>
        <Text className={styles.authFootnote} size={200}>Entorno privado para equipos jurídicos</Text>
      </section>
      <section className={styles.authPanel}>
        <Button className={styles.authThemeToggle} appearance="subtle" icon={<AppIcon name={darkMode ? 'sun' : 'moon'} />} onClick={onToggleTheme}>
          {darkMode ? 'Modo claro' : 'Modo nocturno'}
        </Button>
        <Card className={styles.authCard}>
          <div className={styles.authCardHeading}>
            <div className={styles.securityIcon} aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M12 3 5.5 5.7v5.5c0 4.3 2.7 8.2 6.5 9.8 3.8-1.6 6.5-5.5 6.5-9.8V5.7L12 3Zm0 3.1 3.7 1.5v3.6c0 2.8-1.5 5.5-3.7 6.8-2.2-1.3-3.7-4-3.7-6.8V7.6L12 6.1Z" /></svg>
            </div>
            <div>
              <Text className={styles.authCardTitle} size={600} weight="semibold">{step === 'login' ? 'Ingreso al sistema' : 'Verifique su identidad'}</Text>
              <Text className={styles.muted} block>
                {step === 'login' ? 'Acceda con sus credenciales institucionales.' : `Ingrese el código de seis dígitos enviado a ${email}.`}
              </Text>
            </div>
          </div>
          {(error || offlineMessage) && <MessageBar intent="error"><MessageBarBody>{error || offlineMessage}</MessageBarBody></MessageBar>}
          <form className={styles.formStack} onSubmit={submit}>
          {step === 'login' ? <>
            <Field label="Correo electrónico" required>
              <Input type="email" autoComplete="username" value={email} onChange={(_, data) => setEmail(data.value)} required />
            </Field>
            <Field label="Contraseña" required>
              <Input type="password" autoComplete="current-password" value={password} onChange={(_, data) => setPassword(data.value)} required />
            </Field>
            <div className={styles.captchaBlock}>
              <div className={styles.captchaPrompt}>
                <div>
                  <Text className={styles.captchaLabel} size={200} weight="semibold" block>VERIFICACIÓN DE SEGURIDAD</Text>
                  <Text size={400} weight="semibold">{captchaBusy ? 'Generando desafío…' : `¿Cuánto es ${captchaQuestion}?`}</Text>
                </div>
                <Button className={styles.captchaRefresh} appearance="subtle" size="small" type="button" onClick={() => void loadCaptcha()} disabled={captchaBusy} aria-label="Generar otra suma">↻</Button>
              </div>
              <Field label="Respuesta" required>
                <Input inputMode="numeric" autoComplete="off" placeholder="Ingrese el resultado" value={captcha} onChange={(_, data) => setCaptcha(data.value.replace(/\D/g, '').slice(0, 2))} required />
              </Field>
            </div>
          </> : <Field label="Código de acceso" required hint="El código expira en pocos minutos.">
            <Input className={styles.otpInput} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(_, data) => setCode(data.value.replace(/\D/g, ''))} required />
          </Field>}
          <Button className={styles.authSubmit} appearance="primary" size="large" type="submit" disabled={busy || captchaBusy || (step === 'login' && !captchaQuestion) || (step === 'otp' && code.length !== 6)}>
            {busy ? <Spinner size="tiny" /> : step === 'login' ? 'Continuar de forma segura' : 'Verificar y acceder'}
          </Button>
          {step === 'otp' && <Button appearance="subtle" type="button" onClick={() => { setStep('login'); setCode(''); setError(''); void loadCaptcha() }}>Volver al inicio</Button>}
          </form>
          <div className={styles.authPrivacy}><span aria-hidden="true">●</span> Conexión protegida · Acceso auditado</div>
        </Card>
      </section>
    </main>
  )
}
