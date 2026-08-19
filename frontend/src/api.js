async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.message || `Error HTTP ${response.status}`)
  }
  return data
}

export const api = {
  create: (message) => request('/api/conversations', { method: 'POST', body: JSON.stringify({ message }) }),
  form: (id, answers) => request(`/api/conversations/${id}/form`, { method: 'POST', body: JSON.stringify({ answers }) }),
  revise: (id, instructions) => request(`/api/conversations/${id}/revise`, { method: 'POST', body: JSON.stringify({ instructions }) }),
  approve: (id) => request(`/api/conversations/${id}/approve`, { method: 'POST' }),
  skill: (id, key, answers) => request(`/api/conversations/${id}/skills/${key}`, {
    method: 'POST',
    body: JSON.stringify(answers ? { answers } : {}),
  }),
  exportUrl: (id) => `/api/conversations/${id}/export`,
}
