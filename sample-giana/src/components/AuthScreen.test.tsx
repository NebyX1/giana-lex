import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { clearCsrfToken } from '../api/client'
import { AuthScreen } from './AuthScreen'

beforeEach(() => clearCsrfToken())

test('muestra un error humano cuando las credenciales son incorrectas', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = new URL(String(input), 'http://test').pathname
    if (path === '/api/auth/captcha') return Response.json({ captcha: { question: '2 + 3' } })
    if (path === '/api/auth/csrf') return Response.json({ csrf_token: 'csrf' })
    if (path === '/api/auth/login') {
      return Response.json({ error: 'invalid_credentials', message: 'Credenciales inválidas.', request_id: 'private-ref' }, { status: 401 })
    }
    throw new Error(`Unexpected request ${path}`)
  })

  render(<AuthScreen darkMode={false} onToggleTheme={() => undefined} onAuthenticated={() => undefined} />)
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText(/Correo electrónico/), 'persona@example.test')
  await user.type(screen.getByLabelText(/Contraseña/), 'clave-incorrecta')
  await user.type(screen.getByLabelText(/Respuesta/), '5')
  await user.click(screen.getByRole('button', { name: 'Continuar de forma segura' }))

  expect(await screen.findByText('El correo electrónico o la contraseña no son correctos.')).toBeVisible()
  expect(screen.queryByText(/invalid_credentials|HTTP 401|private-ref/)).not.toBeInTheDocument()
})
