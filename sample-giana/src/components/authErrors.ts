import { ApiError } from '../api/client'

export function authErrorMessage(error: unknown, step: 'login' | 'otp') {
  if (!(error instanceof ApiError)) {
    return error instanceof TypeError
      ? 'No se pudo conectar con el servidor. Verifique que Giana-Lex esté iniciado.'
      : 'No se pudo iniciar sesión. Intente nuevamente.'
  }

  if (error.code === 'invalid_credentials') return 'El correo electrónico o la contraseña no son correctos.'
  if (error.code === 'invalid_captcha') return 'La respuesta de seguridad es incorrecta. Resuelva la nueva suma.'
  if (error.code === 'invalid_verification') return 'El código ingresado es incorrecto o ya venció.'
  if (error.code === 'otp_delivery_failed') return 'No se pudo enviar el código de acceso. Intente nuevamente en unos minutos.'
  if (error.status === 429) return 'Se realizaron demasiados intentos. Espere unos minutos antes de volver a probar.'
  if (error.status >= 500) return 'El servicio de acceso no está disponible en este momento. Intente nuevamente más tarde.'
  return step === 'login' ? 'No se pudo validar el acceso.' : 'No se pudo verificar el código de acceso.'
}
