import { useEffect, useState, type FormEvent } from 'react'
import { Button, Checkbox, Field, Input, MessageBar, MessageBarBody, Select, Spinner, Text, Textarea, Title2, Title3 } from '@fluentui/react-components'
import type { FieldProvenance, FormServerError, WorkspaceDocument } from '../../api/legal'
import type {
  BudgetAllocationComponent,
  BudgetAllocationValue,
  BudgetTransferValue,
  DocumentReferenceValue,
  DocumentType,
  FormFieldDefinition,
  FormValue,
  IntakeSchema,
  LegacyTableValue,
} from './schema'

export type { FormValue } from './schema'

type Props = {
  caseId: string
  schema: IntakeSchema
  initialValues?: Record<string, FormValue>
  initialStatus?: string
  initialErrors?: Record<string, FormServerError>
  provenance?: FieldProvenance[]
  documents?: WorkspaceDocument[]
  precedentSourceUrl?: string | null
  loading?: boolean
  onSave?: (values: Record<string, FormValue>) => void | Promise<void>
  onConfirm?: (values: Record<string, FormValue>) => boolean | void | Promise<boolean | void>
}

const documentTypes: Array<{ value: DocumentType; label: string }> = [
  { value: 'expediente', label: 'Expediente' },
  { value: 'informe_hacienda', label: 'Informe de Hacienda' },
  { value: 'informe_contaduria', label: 'Informe de Contaduría' },
  { value: 'oficio_contaduria', label: 'Oficio de Contaduría' },
  { value: 'oficio', label: 'Oficio' },
  { value: 'resolucion', label: 'Resolución' },
  { value: 'decreto', label: 'Decreto' },
  { value: 'contrato', label: 'Contrato' },
  { value: 'informe_presupuestal', label: 'Informe presupuestal' },
  { value: 'informe_tecnico', label: 'Informe técnico' },
  { value: 'procedimiento_contratacion', label: 'Procedimiento de contratación' },
  { value: 'anexo_presupuestal', label: 'Anexo presupuestal' },
  { value: 'anexo', label: 'Anexo' },
  { value: 'other', label: 'Otro' },
  { value: 'otro', label: 'Otro' },
]

const allocationLabels: Record<BudgetAllocationComponent, string> = {
  identifier: 'Identificador',
  program: 'Programa',
  project: 'Proyecto',
  object: 'Objeto',
  auxiliary: 'Auxiliar',
  financing: 'Financiación',
  unit: 'Unidad',
}

const localizedErrors: Record<string, string> = {
  required: 'Este dato es obligatorio.',
  invalid_shape: 'La estructura del dato no es válida.',
  invalid_value: 'El valor ingresado no es válido.',
  invalid_date: 'La fecha no es válida.',
  must_be_positive: 'El importe debe ser mayor que cero.',
  too_short: 'El dato es demasiado breve.',
  must_be_after: 'La fecha no respeta el orden requerido.',
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function readLocal(storageKey: string): Record<string, FormValue> {
  const stored = window.localStorage.getItem(storageKey)
  if (!stored) return {}
  try {
    const parsed: unknown = JSON.parse(stored)
    if (!isRecord(parsed)) return {}
    const source = isRecord(parsed.values) ? parsed.values : parsed
    return source as Record<string, FormValue>
  } catch {
    return {}
  }
}

function prefilledValues(schema: IntakeSchema) {
  const entries = schema.sections.flatMap((section) => section.fields)
    .filter((field) => field.prefilled_value !== undefined && field.prefilled_value !== null)
    .map((field) => [field.key, field.prefilled_value as FormValue] as const)
  return Object.fromEntries(entries) as Record<string, FormValue>
}

function reconcile(storageKey: string, schema: IntakeSchema, initialValues: Record<string, FormValue>, status?: string) {
  if (status === 'submitted') {
    window.localStorage.removeItem(storageKey)
    return { ...prefilledValues(schema), ...initialValues }
  }
  // Durable answers always win for keys returned by the server; local data only fills absent keys.
  return { ...prefilledValues(schema), ...readLocal(storageKey), ...initialValues }
}

function isBlankDocument(value: DocumentReferenceValue) {
  return !value.number && !value.year && !value.date && !value.issuer && !value.upload_id && !value.source_document_id && !value.source_url && !value.notes && !value.title
}

function isBlank(value: FormValue | undefined) {
  if (value === undefined || value === null || value === '') return true
  if (Array.isArray(value)) return value.length === 0
  if (isRecord(value) && 'document_type' in value) return isBlankDocument(value as DocumentReferenceValue)
  return false
}

function visible(field: FormFieldDefinition, values: Record<string, FormValue>) {
  if (!field.visible_when) return true
  const actual = values[field.visible_when.field]
  return actual === field.visible_when.equals || String(actual ?? '') === String(field.visible_when.equals ?? '')
}

function serverErrorMessage(error: FormServerError) {
  if (typeof error === 'string') return error
  return error.message?.trim() || localizedErrors[error.code ?? ''] || 'El servidor rechazó este dato. Revíselo antes de continuar.'
}

function documentTypeLabel(type: string) {
  return documentTypes.find((item) => item.value === type)?.label ?? type.replaceAll('_', ' ')
}

function asDocument(value: FormValue | undefined, expected?: DocumentType): DocumentReferenceValue {
  if (isRecord(value) && !Array.isArray(value)) return value as DocumentReferenceValue
  return { document_type: expected ?? '' }
}

function asDocuments(value: FormValue | undefined): DocumentReferenceValue[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is DocumentReferenceValue => isRecord(item) && 'document_type' in item)
}

function isBudgetTransfer(value: unknown): value is BudgetTransferValue {
  return isRecord(value) && isRecord(value.origin) && isRecord(value.destination) && typeof value.amount === 'string'
}

function asTransfers(value: FormValue | undefined): BudgetTransferValue[] {
  if (!Array.isArray(value)) return []
  return value.filter(isBudgetTransfer)
}

function normalizeDecimalParts(value: string): { whole: string; fraction: string } | undefined {
  let raw = value.trim().replaceAll(' ', '')
  if (!raw) return undefined
  if (raw.includes(',') && raw.includes('.')) {
    const commaDecimal = raw.lastIndexOf(',') > raw.lastIndexOf('.')
    raw = commaDecimal ? raw.replaceAll('.', '').replace(',', '.') : raw.replaceAll(',', '')
  } else if (raw.includes(',')) {
    const parts = raw.split(',')
    raw = parts.length > 2 || parts.at(-1)?.length === 3 ? parts.join('') : parts.join('.')
  } else if (raw.includes('.')) {
    const parts = raw.split('.')
    if (parts.length > 2 || (parts.length === 2 && parts[1].length === 3)) raw = parts.join('')
  }
  const match = /^([+]?[0-9]+)(?:\.([0-9]{1,2}))?$/.exec(raw)
  if (!match) return undefined
  return { whole: match[1].replace('+', ''), fraction: (match[2] ?? '').padEnd(2, '0') }
}

function decimalCents(value: string): bigint | undefined {
  const parts = normalizeDecimalParts(value)
  if (!parts) return undefined
  return BigInt(parts.whole) * 100n + BigInt(parts.fraction)
}

function formatCents(value: bigint) {
  const whole = (value / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${whole},${(value % 100n).toString().padStart(2, '0')}`
}

function allocationId(value: BudgetAllocationValue, components: BudgetAllocationComponent[]) {
  return components.map((component) => (value[component] ?? '').trim().toLocaleLowerCase('es-UY')).join('|')
}

function validateBudgetRows(rows: BudgetTransferValue[], components: BudgetAllocationComponent[], minimumRows: number) {
  if (rows.length < minimumRows) return `Debe ingresar al menos ${minimumRows === 1 ? 'una fila presupuestal completa' : `${minimumRows} filas presupuestales completas`}.`
  const errors: string[] = []
  const seen = new Set<string>()
  rows.forEach((row, index) => {
    const label = `Fila ${index + 1}`
    const origin = allocationId(row.origin, components)
    const destination = allocationId(row.destination, components)
    const amount = decimalCents(row.amount)
    if (!origin.replaceAll('|', '') || !destination.replaceAll('|', '') || !row.amount.trim()) errors.push(`${label}: complete origen, destino e importe.`)
    else if (amount === undefined) errors.push(`${label}: el importe no es un decimal válido.`)
    else if (amount <= 0n) errors.push(`${label}: el importe debe ser mayor que cero.`)
    if (origin.replaceAll('|', '') && origin === destination) errors.push(`${label}: origen y destino deben ser diferentes.`)
    const duplicateKey = `${origin}>${destination}>${amount?.toString() ?? row.amount}`
    if (seen.has(duplicateKey)) errors.push(`${label}: esta transferencia está duplicada.`)
    seen.add(duplicateKey)
  })
  return errors.join(' ')
}

function validateField(field: FormFieldDefinition, value: FormValue | undefined) {
  if (field.required && isBlank(value)) return 'Este dato es obligatorio.'
  if (isBlank(value)) return ''
  if (typeof value === 'string') {
    if (field.validation_rules?.pattern && !new RegExp(field.validation_rules.pattern).test(value)) return 'El formato no es válido.'
    if (field.validation_rules?.min_length && value.trim().length < field.validation_rules.min_length) return 'El dato es demasiado breve.'
    if (field.field_type === 'number' && field.validation_rules?.integer && !/^\d+$/.test(value)) return 'Ingrese un número entero válido.'
  }
  if (field.field_type === 'document_reference') {
    const references = field.validation_rules?.multiple ? asDocuments(value) : [asDocument(value, field.validation_rules?.document_type)]
    const expected = field.validation_rules?.document_type
    if (field.required && (!references.length || references.some(isBlankDocument))) return 'Incluya al menos un dato que identifique el documento.'
    const mismatch = expected && references.find((reference) => reference.document_type && reference.document_type !== expected)
    if (mismatch) return `${field.label} requiere ${documentTypeLabel(expected)}; el tipo seleccionado es ${documentTypeLabel(mismatch.document_type)}.`
  }
  if (field.field_type === 'budget_transfer_table') {
    return validateBudgetRows(asTransfers(value), field.validation_rules?.allocation_components ?? ['identifier'], field.validation_rules?.min_rows ?? 1)
  }
  return ''
}

function provenanceLabel(sourceType: string) {
  const labels: Record<string, string> = {
    workflow: 'Definido por la ruta del trámite.',
    validated_precedent_structure: 'Estructura tomada de un antecedente validado.',
    user_message: 'Aportado explícitamente en su mensaje.',
    persisted_fact: 'Dato ya registrado en el expediente.',
    uploaded_document: 'Vinculado a un documento cargado en el expediente.',
    user_answer: 'Respuesta guardada en el expediente.',
  }
  return labels[sourceType] ?? 'Origen registrado en el expediente.'
}

export function SchemaForm({ caseId, schema, initialValues = {}, initialStatus, initialErrors = {}, provenance = [], documents = [], precedentSourceUrl, loading, onSave, onConfirm }: Props) {
  const storageKey = `giana-lex:intake:${caseId}:${schema.id ?? 'current'}:${schema.version ?? 1}`
  const schemaSignature = JSON.stringify(schema)
  const valuesSignature = JSON.stringify(initialValues)
  const errorsSignature = JSON.stringify(initialErrors)
  const [values, setValues] = useState<Record<string, FormValue>>(() => reconcile(storageKey, schema, initialValues, initialStatus))
  const [errors, setErrors] = useState<Record<string, string>>(() => Object.fromEntries(Object.entries(initialErrors).map(([key, error]) => [key, serverErrorMessage(error)])))
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const currentSchema = JSON.parse(schemaSignature) as IntakeSchema
    const currentValues = JSON.parse(valuesSignature) as Record<string, FormValue>
    const currentErrors = JSON.parse(errorsSignature) as Record<string, FormServerError>
    setValues(reconcile(storageKey, currentSchema, currentValues, initialStatus))
    setErrors(Object.fromEntries(Object.entries(currentErrors).map(([key, error]) => [key, serverErrorMessage(error)])))
    setSaved(false)
  }, [storageKey, schemaSignature, valuesSignature, errorsSignature, initialStatus])

  function set(key: string, value: FormValue) {
    setValues((current) => ({ ...current, [key]: value }))
    setErrors((current) => Object.fromEntries(Object.entries(current).filter(([field]) => field !== key)))
    setSaved(false)
  }

  function persistLocal() {
    window.localStorage.setItem(storageKey, JSON.stringify(values))
    setSaved(true)
  }

  async function save() {
    persistLocal()
    await onSave?.(values)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const next: Record<string, string> = {}
    for (const field of schema.sections.flatMap((section) => section.fields)) {
      if (!visible(field, values)) continue
      const message = validateField(field, values[field.key])
      if (message) next[field.key] = message
    }
    setErrors(next)
    if (Object.keys(next).length) return
    persistLocal()
    const submitted = await onConfirm?.(values)
    if (submitted === true) {
      window.localStorage.removeItem(storageKey)
      setSaved(false)
    }
  }

  const errorEntries = Object.entries(errors)
  if (loading) return <Spinner label="Guardando datos del expediente" />
  return <form className="legal-form" onSubmit={(event) => void submit(event)} noValidate>
    {(schema.title || schema.description) && <header className="legal-form-heading">{schema.title && <Title2 as="h2">{schema.title}</Title2>}{schema.description && <Text className="legal-muted">{schema.description}</Text>}</header>}
    {errorEntries.length > 0 && <MessageBar intent="error"><MessageBarBody><Text weight="semibold" block>Revise {errorEntries.length === 1 ? 'el dato señalado' : 'los datos señalados'}:</Text><ul className="legal-error-summary">{errorEntries.map(([key, message]) => <li key={key}><a href={`#field-${key}`}>{message}</a></li>)}</ul></MessageBarBody></MessageBar>}
    {schema.sections.map((section) => <section className="legal-form-section" aria-labelledby={`section-${section.id}`} key={section.id}>
      <Title3 as="h3" id={`section-${section.id}`}>{section.title}</Title3>
      {section.description && <Text className="legal-muted">{section.description}</Text>}
      <div className="legal-form-grid">{section.fields.filter((field) => visible(field, values)).map((field) => {
        const source = field.provenance ?? provenance.find((item) => item.field_key === field.key)
        return <SchemaField key={field.key} field={field} value={values[field.key]} error={errors[field.key]} documents={documents} provenance={source} precedentSourceUrl={precedentSourceUrl} setValue={(value) => set(field.key, value)} />
      })}</div>
    </section>)}
    {saved && <MessageBar intent="success"><MessageBarBody>Borrador guardado en este dispositivo y enviado al expediente cuando corresponde.</MessageBarBody></MessageBar>}
    <div className="legal-form-actions"><Button type="button" onClick={() => void save()}>Guardar borrador</Button><Button appearance="primary" type="submit">Confirmar datos</Button></div>
  </form>
}

function Provenance({ field, provenance, precedentSourceUrl }: { field: FormFieldDefinition; provenance?: FieldProvenance; precedentSourceUrl?: string | null }) {
  const sourceType = provenance?.source_type ?? field.provenance?.source_type ?? field.origin
  if (!sourceType && !field.reason) return null
  const reason = provenance?.reason ?? field.provenance?.reason ?? field.reason
  return <div className="legal-provenance"><Text size={200}>{sourceType ? provenanceLabel(sourceType) : 'Dato requerido para este trámite.'}</Text>{sourceType === 'validated_precedent_structure' && precedentSourceUrl && <a href={precedentSourceUrl} target="_blank" rel="noreferrer">Consultar fuente del antecedente</a>}{reason && <Text size={200}>{reason}</Text>}{(field.prefilled_value !== undefined || provenance?.value_json?.value !== undefined) && provenance?.requires_confirmation !== false && <Text size={200} weight="semibold">Valor precompletado: confirme que sigue siendo correcto.</Text>}</div>
}

function SchemaField({ field, value, error, documents, provenance, precedentSourceUrl, setValue }: { field: FormFieldDefinition; value?: FormValue; error?: string; documents: WorkspaceDocument[]; provenance?: FieldProvenance; precedentSourceUrl?: string | null; setValue: (value: FormValue) => void }) {
  const options = (field.options ?? []).map((option) => typeof option === 'string' ? { label: option, value: option } : option)
  const invalid = Boolean(error)
  if (field.field_type === 'boolean') return <div id={`field-${field.key}`}><Field validationMessage={error} validationState={invalid ? 'error' : 'none'}><Checkbox label={field.label} checked={Boolean(value)} required={field.required} aria-invalid={invalid} onChange={(_, data) => setValue(Boolean(data.checked))} /></Field><Provenance field={field} provenance={provenance} precedentSourceUrl={precedentSourceUrl} /></div>
  if (field.field_type === 'document_reference') return <DocumentField field={field} value={value} documents={documents} setValue={setValue} error={error} provenance={provenance} precedentSourceUrl={precedentSourceUrl} />
  if (field.field_type === 'budget_transfer_table') return <BudgetTransferField field={field} value={asTransfers(value)} setValue={setValue} error={error} provenance={provenance} precedentSourceUrl={precedentSourceUrl} />
  if (field.field_type === 'person_table' || field.field_type === 'budget_table') return <LegacyTableField field={field} value={Array.isArray(value) ? value.filter((item): item is Record<string, string> => isRecord(item) && Object.values(item).every((entry) => typeof entry === 'string')) : []} setValue={setValue} error={error} />
  return <div id={`field-${field.key}`}><Field label={field.label} required={field.required} validationMessage={error} validationState={invalid ? 'error' : 'none'}>
    {field.field_type === 'textarea' ? <Textarea value={typeof value === 'string' ? value : ''} aria-invalid={invalid} onChange={(_, data) => setValue(data.value)} />
      : field.field_type === 'select' ? <Select value={typeof value === 'string' ? value : ''} aria-invalid={invalid} onChange={(_, data) => setValue(data.value)}><option value="">Seleccionar</option>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select>
        : field.field_type === 'multiselect' ? <select multiple aria-label={field.label} aria-invalid={invalid} value={Array.isArray(value) && value.every((item) => typeof item === 'string') ? value : []} onChange={(event) => setValue([...event.currentTarget.selectedOptions].map((option) => option.value))}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
          : <Input type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'} inputMode={field.field_type === 'currency' ? 'decimal' : undefined} value={typeof value === 'string' ? value : value === null || value === undefined ? '' : String(value)} min={field.validation_rules?.min} max={field.validation_rules?.max} aria-invalid={invalid} onChange={(_, data) => setValue(data.value)} />}
  </Field><Provenance field={field} provenance={provenance} precedentSourceUrl={precedentSourceUrl} /></div>
}

function DocumentField({ field, value, documents, setValue, error, provenance, precedentSourceUrl }: { field: FormFieldDefinition; value?: FormValue; documents: WorkspaceDocument[]; setValue: (value: FormValue) => void; error?: string; provenance?: FieldProvenance; precedentSourceUrl?: string | null }) {
  const multiple = Boolean(field.validation_rules?.multiple)
  const references = multiple ? asDocuments(value) : [asDocument(value, field.validation_rules?.document_type)]
  function update(index: number, patch: Partial<DocumentReferenceValue>) {
    const next = references.map((reference, itemIndex) => itemIndex === index ? { ...reference, ...patch } : reference)
    setValue(multiple ? next : next[0])
  }
  function add() {
    setValue([...references, { document_type: field.validation_rules?.document_type ?? '' }])
  }
  return <fieldset id={`field-${field.key}`} className="legal-table-field legal-document-field" aria-invalid={Boolean(error)}><legend>{field.label}{field.required ? ' *' : ''}</legend><Provenance field={field} provenance={provenance} precedentSourceUrl={precedentSourceUrl} />
    {references.map((reference, index) => <div className="legal-document-reference" key={index}><div className="legal-row-heading"><Text weight="semibold">{multiple ? `Documento ${index + 1}` : 'Referencia documental'}</Text>{multiple && <Button type="button" size="small" onClick={() => setValue(references.filter((_, itemIndex) => itemIndex !== index))}>Quitar</Button>}</div><div className="legal-document-grid">
      <Field label="Tipo de documento" required><Select aria-invalid={Boolean(error)} value={reference.document_type} onChange={(_, data) => update(index, { document_type: data.value as DocumentType | '' })}><option value="">Seleccionar tipo</option>{documentTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</Select></Field>
      <Field label="Número"><Input value={reference.number ?? ''} onChange={(_, data) => update(index, { number: data.value })} /></Field>
      <Field label="Año"><Input type="number" min={1800} max={2200} value={String(reference.year ?? '')} onChange={(_, data) => update(index, { year: data.value })} /></Field>
      <Field label="Fecha"><Input type="date" value={reference.date ?? ''} onChange={(_, data) => update(index, { date: data.value })} /></Field>
      <Field label="Emisor" hint={field.validation_rules?.issuer_help}><Input value={reference.issuer ?? ''} onChange={(_, data) => update(index, { issuer: data.value })} /></Field>
      <Field label="Documento cargado"><Select value={String(reference.upload_id ?? '')} onChange={(_, data) => { const id = data.value ? Number(data.value) : undefined; update(index, { upload_id: id, source_document_id: id }) }}><option value="">Sin documento vinculado</option>{documents.map((document) => <option key={document.id} value={document.id}>{document.original_name}</option>)}</Select></Field>
      <Field label="URL de origen"><Input type="url" value={reference.source_url ?? ''} onChange={(_, data) => update(index, { source_url: data.value })} /></Field>
      <Field label="Notas"><Textarea value={reference.notes ?? ''} onChange={(_, data) => update(index, { notes: data.value })} /></Field>
    </div></div>)}
    {multiple && <Button type="button" onClick={add}>Agregar documento</Button>}{error && <Text role="alert" className="legal-field-error">{error}</Text>}
  </fieldset>
}

function BudgetTransferField({ field, value, setValue, error, provenance, precedentSourceUrl }: { field: FormFieldDefinition; value: BudgetTransferValue[]; setValue: (value: FormValue) => void; error?: string; provenance?: FieldProvenance; precedentSourceUrl?: string | null }) {
  const components = field.validation_rules?.allocation_components ?? ['identifier']
  const total = value.reduce((sum, row) => sum + (decimalCents(row.amount) ?? 0n), 0n)
  function update(index: number, patch: Partial<BudgetTransferValue>) {
    setValue(value.map((row, itemIndex) => itemIndex === index ? { ...row, ...patch } : row))
  }
  function updateAllocation(index: number, side: 'origin' | 'destination', component: BudgetAllocationComponent, nextValue: string) {
    const row = value[index]
    update(index, { [side]: { ...row[side], [component]: nextValue } })
  }
  return <fieldset id={`field-${field.key}`} className="legal-table-field legal-budget-field" aria-invalid={Boolean(error)}><legend>{field.label}{field.required ? ' *' : ''}</legend><Provenance field={field} provenance={provenance} precedentSourceUrl={precedentSourceUrl} />
    {value.map((row, index) => <div className="legal-budget-row" aria-label={`Transferencia presupuestal ${index + 1}`} key={index}><div className="legal-row-heading"><Text weight="semibold">Transferencia {index + 1}</Text><Button type="button" size="small" aria-label={`Eliminar transferencia ${index + 1}`} onClick={() => setValue(value.filter((_, itemIndex) => itemIndex !== index))}>Quitar</Button></div><div className="legal-allocation-columns">
      <section aria-label={`Origen de transferencia ${index + 1}`}><Text weight="semibold">Asignación de origen</Text>{components.map((component) => <Field label={allocationLabels[component]} key={component}><Input value={row.origin[component] ?? ''} onChange={(_, data) => updateAllocation(index, 'origin', component, data.value)} /></Field>)}</section>
      <section aria-label={`Destino de transferencia ${index + 1}`}><Text weight="semibold">Asignación de destino</Text>{components.map((component) => <Field label={allocationLabels[component]} key={component}><Input value={row.destination[component] ?? ''} onChange={(_, data) => updateAllocation(index, 'destination', component, data.value)} /></Field>)}</section>
    </div><Field label={`Importe de transferencia ${index + 1}`} required><Input inputMode="decimal" aria-invalid={Boolean(error)} value={row.amount} onChange={(_, data) => update(index, { amount: data.value })} /></Field></div>)}
    <div className="legal-budget-footer"><Button type="button" onClick={() => setValue([...value, { origin: {}, destination: {}, amount: '' }])}>Agregar transferencia</Button><Text weight="semibold" aria-live="polite">Total: {formatCents(total)}</Text></div>{error && <Text role="alert" className="legal-field-error">{error}</Text>}
  </fieldset>
}

function LegacyTableField({ field, value, setValue, error }: { field: FormFieldDefinition; value: LegacyTableValue; setValue: (value: FormValue) => void; error?: string }) {
  const columns = field.field_type === 'person_table' ? ['nombre', 'documento'] : ['partida', 'importe']
  return <fieldset id={`field-${field.key}`} className="legal-table-field" aria-invalid={Boolean(error)}><legend>{field.label}{field.required ? ' *' : ''}</legend>{field.reason && <Text className="legal-muted" size={200}>{field.reason}</Text>}
    {value.map((row, index) => <div className="legal-table-row" key={index}>{columns.map((column) => <Input key={column} aria-label={`${column} ${index + 1}`} placeholder={column} value={row[column] ?? ''} onChange={(_, data) => setValue(value.map((item, itemIndex) => itemIndex === index ? { ...item, [column]: data.value } : item))} />)}<Button type="button" aria-label={`Eliminar fila ${index + 1}`} onClick={() => setValue(value.filter((_, itemIndex) => itemIndex !== index))}>Quitar</Button></div>)}
    <Button type="button" onClick={() => setValue([...value, Object.fromEntries(columns.map((column) => [column, '']))])}>Agregar fila</Button>{error && <Text role="alert" className="legal-field-error">{error}</Text>}
  </fieldset>
}
