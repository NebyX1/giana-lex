import { expect, test } from 'vitest'
import { ApiError } from '../api/client'
import { authErrorMessage } from './authErrors'

test('traduce errores de autenticación sin detalles técnicos', () => {
  const invalid = new ApiError('Credenciales inválidas.', 401, 'invalid_credentials', 'request-secret')
  expect(authErrorMessage(invalid, 'login')).toBe('El correo electrónico o la contraseña no son correctos.')
  expect(authErrorMessage(invalid, 'login')).not.toMatch(/HTTP|request|invalid_credentials/)

  expect(authErrorMessage(new ApiError('Código inválido.', 401, 'invalid_verification'), 'otp'))
    .toBe('El código ingresado es incorrecto o ya venció.')
  expect(authErrorMessage(new ApiError('Rate limited.', 429), 'login'))
    .toMatch(/demasiados intentos/i)
})
