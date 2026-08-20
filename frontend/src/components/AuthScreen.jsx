import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Field, Input, MessageBar, MessageBarBody, Spinner, Text } from '@fluentui/react-components'
import { ShieldCheckmarkRegular, WeatherMoonRegular, WeatherSunnyRegular } from '@fluentui/react-icons'
import { authApi } from '../api.js'

export default function AuthScreen({ darkMode, onToggleTheme, onAuthenticated }) {
  const [step, setStep] = useState('login')
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
      const response = await authApi.captcha()
      setCaptchaQuestion(response.captcha.question)
    } catch {
      setCaptchaQuestion('')
      if (reportError) setError('No se pudo cargar la verificación de seguridad.')
    } finally { setCaptchaBusy(false) }
  }, [])

  useEffect(() => { void loadCaptcha() }, [loadCaptcha])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (step === 'login') {
        await authApi.login(email, password, captcha)
        setStep('otp')
      } else {
        const response = await authApi.verify(code)
        onAuthenticated(response.user)
      }
    } catch (caught) {
      setError(caught.message || 'No se pudo completar el acceso.')
      if (step === 'login') await loadCaptcha(false)
    } finally { setBusy(false) }
  }

  return <main className="auth-page">
    <section className="auth-intro"><div className="auth-glow" aria-hidden="true" /><div className="brand-lockup"><div className="brand-mark-light">GL</div><div><strong>GIANA-LEX</strong><small>Inteligencia jurídica</small></div></div><div className="auth-pitch"><span className="auth-eyebrow">PLATAFORMA DE TRABAJO JURÍDICO</span><h1>Rigor jurídico, respaldado por evidencia.</h1><p>Investigue normativa, prepare documentos y revise expedientes con fuentes verificables y control profesional en cada etapa.</p></div><div className="trust-list"><span>Fuentes verificables</span><span>Trazabilidad integral</span><span>Revisión humana</span></div><small className="auth-footnote">Entorno privado para equipos jurídicos</small></section>
    <section className="auth-panel"><Button className="auth-theme" appearance="subtle" icon={darkMode ? <WeatherSunnyRegular /> : <WeatherMoonRegular />} onClick={onToggleTheme}>{darkMode ? 'Modo claro' : 'Modo nocturno'}</Button><Card className="auth-card"><div className="auth-card-heading"><div className="security-icon"><ShieldCheckmarkRegular /></div><div><Text size={600} weight="semibold" block>{step === 'login' ? 'Ingreso al sistema' : 'Verifique su identidad'}</Text><Text className="muted" block>{step === 'login' ? 'Acceda con sus credenciales institucionales.' : `Ingrese el código de seis dígitos enviado a ${email}.`}</Text></div></div>{error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}<form className="form-stack" onSubmit={submit}>{step === 'login' ? <><Field label="Correo electrónico" required><Input type="email" autoComplete="username" value={email} onChange={(_, data) => setEmail(data.value)} required /></Field><Field label="Contraseña" required><Input type="password" autoComplete="current-password" value={password} onChange={(_, data) => setPassword(data.value)} required /></Field><div className="captcha-block"><div className="captcha-prompt"><div><small>VERIFICACIÓN DE SEGURIDAD</small><strong>{captchaBusy ? 'Generando desafío…' : `¿Cuánto es ${captchaQuestion}?`}</strong></div><Button appearance="subtle" type="button" disabled={captchaBusy} aria-label="Generar otra suma" onClick={() => void loadCaptcha()}>↻</Button></div><Field label="Respuesta" required><Input inputMode="numeric" value={captcha} onChange={(_, data) => setCaptcha(data.value.replace(/\D/g, '').slice(0, 2))} required /></Field></div></> : <Field label="Código de acceso" hint="El código expira en pocos minutos." required><Input className="otp-input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(_, data) => setCode(data.value.replace(/\D/g, ''))} required /></Field>}<Button className="auth-submit" appearance="primary" size="large" type="submit" disabled={busy || captchaBusy || (step === 'otp' && code.length !== 6)}>{busy ? <Spinner size="tiny" /> : step === 'login' ? 'Continuar de forma segura' : 'Verificar y acceder'}</Button>{step === 'otp' && <Button appearance="subtle" type="button" onClick={() => { setStep('login'); setCode(''); setError(''); void loadCaptcha() }}>Volver al inicio</Button>}</form><div className="auth-privacy"><span>●</span> Conexión protegida · Acceso auditado</div></Card></section>
  </main>
}
