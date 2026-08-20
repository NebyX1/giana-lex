import { FluentProvider, webLightTheme } from '@fluentui/react-components'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { CaseListPage } from './CaseListPage'
import { expect, test, vi } from 'vitest'

test('crea un expediente y abre su workspace', async () => {
  const user = userEvent.setup()
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/api/legal/cases') && !init?.method) return Response.json({ cases: [] })
    if (url.endsWith('/api/auth/csrf')) return Response.json({ csrf_token: 'csrf' })
    if (url.endsWith('/api/legal/cases') && init?.method === 'POST') return Response.json({ case: { id: 'new-case' } }, { status: 201 })
    throw new Error(`Unexpected request ${url}`)
  })
  render(<FluentProvider theme={webLightTheme}><MemoryRouter initialEntries={['/cases']}><Routes><Route path="/cases" element={<CaseListPage />} /><Route path="/cases/:caseId" element={<div>Workspace abierto</div>} /></Routes></MemoryRouter></FluentProvider>)
  await screen.findByText('No hay expedientes')
  await user.click(screen.getByRole('button', { name: 'Nuevo expediente' }))
  await user.type(screen.getByLabelText(/Título/), 'Renovación 2026')
  fireEvent.submit(screen.getByLabelText(/Título/).closest('form')!)
  expect(await screen.findByText('Workspace abierto')).toBeInTheDocument()
})
