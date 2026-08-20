let csrfToken
let csrfRequest

export class ApiError extends Error {
  constructor(message, status, code, requestId) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

async function getCsrfToken() {
  if (csrfToken) return csrfToken
  if (!csrfRequest) {
    csrfRequest = fetch('/api/auth/csrf', { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new ApiError('No se pudo iniciar una conexión segura.', response.status)
        const body = await response.json()
        csrfToken = body.csrf_token
        return csrfToken
      })
      .finally(() => { csrfRequest = undefined })
  }
  return csrfRequest
}

export function clearCsrfToken() { csrfToken = undefined }

export async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  const headers = { ...(isFormData ? {} : options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers['X-CSRFToken'] = await getCsrfToken()
  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })
  if (response.status === 204) return undefined
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(data.message || `Error HTTP ${response.status}`, response.status, data.error, data.request_id || response.headers.get('X-Request-ID'))
  }
  return data
}

export const api = {
  create: (message) => request('/api/conversations', { method: 'POST', body: JSON.stringify({ message }) }),
  list: () => request('/api/conversations'),
  get: (id) => request(`/api/conversations/${id}`),
  form: (id, answers) => request(`/api/conversations/${id}/form`, { method: 'POST', body: JSON.stringify({ answers }) }),
  revise: (id, instructions) => request(`/api/conversations/${id}/revise`, { method: 'POST', body: JSON.stringify({ instructions }) }),
  approve: (id) => request(`/api/conversations/${id}/approve`, { method: 'POST' }),
  skill: (id, key, answers) => request(`/api/conversations/${id}/skills/${key}`, {
    method: 'POST',
    body: JSON.stringify(answers ? { answers } : {}),
  }),
  exportUrl: (id) => `/api/conversations/${id}/export`,
}

export const authApi = {
  me: () => request('/api/auth/me'),
  captcha: () => request('/api/auth/captcha'),
  login: (email, password, captcha) => request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password, captcha }) }),
  verify: (code) => request('/api/auth/verify', { method: 'POST', body: JSON.stringify({ code }) }),
  logout: async () => { try { return await request('/api/auth/logout', { method: 'POST' }) } finally { clearCsrfToken() } },
}

const queryString = (params) => {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) query.set(key, value)
  })
  return query.toString()
}

export const knowledgeApi = {
  overview: () => request('/api/settings/legal/overview'),
  taxonomy: (params = {}) => request(`/api/settings/legal/taxonomy?${queryString(params)}`),
  taxonomyDetail: (id) => request(`/api/settings/legal/taxonomy/${id}`),
  createTaxonomy: (data) => request('/api/settings/legal/taxonomy', { method: 'POST', body: JSON.stringify(data) }),
  updateTaxonomy: (id, data) => request(`/api/settings/legal/taxonomy/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  duplicateTaxonomy: (id, data) => request(`/api/settings/legal/taxonomy/${id}/duplicate`, { method: 'POST', body: JSON.stringify(data) }),
  reindexTaxonomy: (id) => request(`/api/settings/legal/taxonomy/${id}/reindex`, { method: 'POST' }),
  resolutions: (params = {}) => request(`/api/settings/legal/resolutions?${queryString(params)}`),
  resolution: (id) => request(`/api/settings/legal/resolutions/${id}`),
  createResolution: (data) => request('/api/settings/legal/resolutions', { method: 'POST', body: JSON.stringify(data) }),
  updateResolution: (id, data) => request(`/api/settings/legal/resolutions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  importUrl: (data) => request('/api/settings/legal/resolutions/import-url', { method: 'POST', body: JSON.stringify(data) }),
  importFile: (file, metadata) => { const body = new FormData(); body.append('file', file); body.append('metadata', JSON.stringify(metadata)); return request('/api/settings/legal/resolutions/import-file', { method: 'POST', body }) },
  reindexResolution: (id) => request(`/api/settings/legal/resolutions/${id}/reindex`, { method: 'POST' }),
  indexStatus: () => request('/api/settings/legal/index/status'),
  retryFailed: () => request('/api/settings/legal/index/retry-failed', { method: 'POST' }),
  checkIndex: () => request('/api/settings/legal/index/check', { method: 'POST' }),
}
