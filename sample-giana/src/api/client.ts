import type { AgentEvent } from '../types'

const configuredBase = import.meta.env.VITE_API_URL?.replace(/\/$/, '')
const API_BASE = configuredBase ?? (window.location.protocol === 'file:' ? 'http://127.0.0.1:5000' : '')

export function apiUrl(path: string) {
  return `${API_BASE}${path}`
}

let csrfToken: string | undefined
let csrfRequest: Promise<string> | undefined

export class ApiError extends Error {
  status: number
  code?: string
  requestId?: string

  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }

  diagnosticMessage() {
    const details = [this.code && `error: ${this.code}`, `HTTP ${this.status}`, this.requestId && `ref: ${this.requestId}`]
      .filter(Boolean)
      .join(' | ')
    return `${this.message} (${details})`
  }
}

async function getCsrfToken() {
  if (csrfToken) return csrfToken
  if (!csrfRequest) {
    csrfRequest = fetch(`${API_BASE}/api/auth/csrf`, { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new ApiError('No se pudo iniciar una conexión segura.', response.status)
        const body = (await response.json()) as { csrf_token: string }
        csrfToken = body.csrf_token
        return body.csrf_token
      })
      .finally(() => { csrfRequest = undefined })
  }
  return csrfRequest
}

async function parseError(response: Response) {
  const body = await response.json().catch(() => null) as {
    error?: string
    message?: string
    request_id?: string
  } | null
  const requestId = body?.request_id || response.headers.get('X-Request-ID') || undefined
  return new ApiError(
    body?.message || 'El servidor no pudo completar la solicitud.',
    response.status,
    body?.error,
    requestId,
  )
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers.set('X-CSRFToken', await getCsrfToken())

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function uploadDocument(sessionId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return apiRequest<{ id: number; filename: string; mime_type: string; size_bytes: number }>(
    `/api/documents/sessions/${sessionId}`,
    { method: 'POST', body: form },
  )
}

export async function downloadFile(path: string, filename: string) {
  const response = await fetch(`${API_BASE}${path}`, { credentials: 'include' })
  if (!response.ok) throw await parseError(response)
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export async function streamRequest(
  path: string,
  body: unknown,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    signal,
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
      'X-CSRFToken': await getCsrfToken(),
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await parseError(response)
  if (!response.body) throw new ApiError('El servidor no inició la transmisión.', 502)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      let event = 'message'
      const data: string[] = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      }
      if (data.length) {
        const parsed = JSON.parse(data.join('\n')) as Record<string, unknown>
        onEvent({ event, data: parsed })
      }
    }
    if (done) break
  }
}

export function clearCsrfToken() {
  csrfToken = undefined
}
