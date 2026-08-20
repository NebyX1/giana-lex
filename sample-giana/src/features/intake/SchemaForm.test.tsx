import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import type { IntakeSchema } from './schema'
import { SchemaForm } from './SchemaForm'

const schema: IntakeSchema = { sections: [{ id: 'base', title: 'Datos básicos', fields: [
  { key: 'name', label: 'Nombre', field_type: 'text', required: true },
  { key: 'detail', label: 'Detalle', field_type: 'textarea', visible_when: { field: 'enabled', equals: true } },
  { key: 'enabled', label: 'Agregar detalle', field_type: 'boolean' },
] }] }

beforeEach(() => window.localStorage.clear())

test('trata null como vacío requerido, muestra resumen y aria-invalid', async () => {
  render(<SchemaForm caseId="case-null" schema={schema} initialValues={{ name: null }} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Confirmar datos' }))
  expect(screen.getAllByText('Este dato es obligatorio.')).toHaveLength(2)
  expect(screen.getByLabelText(/Nombre/)).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByText(/Revise el dato señalado/)).toBeVisible()
})

test('mantiene editable el parcial y no deja que el borrador local pise respuestas durables', async () => {
  const storageKey = 'giana-lex:intake:case-partial:current:1'
  window.localStorage.setItem(storageKey, JSON.stringify({ name: 'Valor local viejo', detail: 'Detalle local' }))
  const { rerender } = render(<SchemaForm caseId="case-partial" schema={schema} initialStatus="partial" initialValues={{ name: 'Valor durable' }} />)
  const name = screen.getByLabelText(/Nombre/)
  expect(name).toHaveValue('Valor durable')
  await userEvent.setup().clear(name)
  await userEvent.setup().type(name, 'Valor editado')
  expect(screen.getByRole('button', { name: 'Guardar borrador' })).toBeEnabled()

  rerender(<SchemaForm caseId="case-partial" schema={schema} initialStatus="partial" initialValues={{ name: 'Valor durable más nuevo' }} />)
  expect(screen.getByLabelText(/Nombre/)).toHaveValue('Valor durable más nuevo')
})

test('presenta el título y el error documental específico entregados por el servidor', () => {
  const documentSchema: IntakeSchema = { title: 'Datos para la trasposición presupuestal', sections: [{ id: 'docs', title: 'Documentos de origen', fields: [{
    key: 'informe_hacienda', label: 'Informe de la Dirección General de Hacienda', field_type: 'document_reference', required: true,
    reason: 'Individualiza el informe que respalda el movimiento.', validation_rules: { document_type: 'informe_hacienda' },
  }] }] }
  render(<SchemaForm caseId="case-doc" schema={documentSchema} initialValues={{ informe_hacienda: { document_type: 'resolucion', number: '2.629/026' } }} initialErrors={{ informe_hacienda: { code: 'invalid_value', message: 'El campo requiere un Informe de Hacienda; una Resolución no coincide con ese tipo documental.' } }} />)
  expect(screen.getByRole('heading', { name: 'Datos para la trasposición presupuestal' })).toBeVisible()
  expect(screen.getAllByText(/una Resolución no coincide/)).toHaveLength(2)
  expect(screen.getByLabelText(/Tipo de documento/)).toHaveValue('resolucion')
})

test('gestiona varias transferencias, calcula centavos sin float y detecta duplicados', async () => {
  const budgetSchema: IntakeSchema = { sections: [{ id: 'budget', title: 'Movimientos presupuestales', fields: [{
    key: 'budget_transfers', label: 'Trasposiciones presupuestales', field_type: 'budget_transfer_table', required: true,
    reason: 'Cada fila contiene origen, destino e importe.', validation_rules: { min_rows: 1, allocation_components: ['identifier'] },
  }] }] }
  const rows = [
    { origin: { identifier: 'A' }, destination: { identifier: 'B' }, amount: '0,10' },
    { origin: { identifier: 'C' }, destination: { identifier: 'D' }, amount: '0,20' },
    { origin: { identifier: 'A' }, destination: { identifier: 'B' }, amount: '0,10' },
  ]
  render(<SchemaForm caseId="case-budget" schema={budgetSchema} initialValues={{ budget_transfers: rows }} />)
  expect(screen.getByText('Total: 0,40')).toBeVisible()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Agregar transferencia' }))
  expect(screen.getAllByLabelText(/Transferencia presupuestal/)).toHaveLength(4)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Eliminar transferencia 4' }))
  await userEvent.setup().click(screen.getByRole('button', { name: 'Confirmar datos' }))
  expect(screen.getAllByText(/transferencia está duplicada/)).toHaveLength(2)
})

test('localiza procedencia, conserva razones específicas y enlaza la fuente validada', () => {
  const provenanceSchema: IntakeSchema = { sections: [{ id: 'base', title: 'Datos', fields: [{ key: 'unit', label: 'Unidad', field_type: 'text', reason: 'Identifica la unidad solicitante.' }] }] }
  render(<SchemaForm caseId="case-provenance" schema={provenanceSchema} initialValues={{ unit: 'Hacienda' }} provenance={[{ id: 'prov-1', field_key: 'unit', source_type: 'validated_precedent_structure', source_ref: 'example-1', reason: 'Razón específica para la unidad.', value_json: { value: 'Hacienda' }, requires_confirmation: true }]} precedentSourceUrl="https://example.test/oficial" />)
  expect(screen.getByText('Estructura tomada de un antecedente validado.')).toBeVisible()
  expect(screen.getByText('Razón específica para la unidad.')).toBeVisible()
  expect(screen.getByText(/Valor precompletado/)).toBeVisible()
  expect(screen.getByRole('link', { name: 'Consultar fuente del antecedente' })).toHaveAttribute('href', 'https://example.test/oficial')
  expect(screen.queryByText('validated_precedent_structure')).not.toBeInTheDocument()
})

test('conserva formularios condicionales y tablas legacy', async () => {
  const legacy: IntakeSchema = { sections: [{ id: 'legacy', title: 'Formulario anterior', fields: [
    ...schema.sections[0].fields,
    { key: 'people', label: 'Personas', field_type: 'person_table' },
  ] }] }
  render(<SchemaForm caseId="case-legacy" schema={legacy} />)
  const user = userEvent.setup()
  expect(screen.queryByLabelText('Detalle')).not.toBeInTheDocument()
  await user.click(screen.getByLabelText('Agregar detalle'))
  expect(screen.getByLabelText('Detalle')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Agregar fila' }))
  const table = screen.getByRole('group', { name: 'Personas' })
  expect(within(table).getByLabelText('nombre 1')).toBeVisible()
  await user.type(screen.getByLabelText(/^Nombre/), 'Ana')
  await user.click(screen.getByRole('button', { name: 'Guardar borrador' }))
  expect(window.localStorage.getItem('giana-lex:intake:case-legacy:current:1')).toContain('Ana')
})

test('limpia el borrador local después de una entrega confirmada', async () => {
  const onConfirm = vi.fn().mockResolvedValue(true)
  render(<SchemaForm caseId="case-submitted" schema={schema} initialValues={{ name: 'Ana' }} onConfirm={onConfirm} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Confirmar datos' }))
  expect(onConfirm).toHaveBeenCalled()
  expect(window.localStorage.getItem('giana-lex:intake:case-submitted:current:1')).toBeNull()
})
