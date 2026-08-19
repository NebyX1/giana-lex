import { useEffect, useState } from 'react'
import {
  Button,
  Checkbox,
  Dropdown,
  Field,
  Input,
  Option,
  Textarea,
} from '@fluentui/react-components'

export default function DynamicForm({ form, onSubmit, busy, submitLabel = 'Continuar' }) {
  const [values, setValues] = useState({})

  useEffect(() => {
    const defaults = Object.fromEntries(form.fields.filter((field) => field.field_type === 'boolean').map((field) => [field.id, false]))
    setValues(defaults)
  }, [form])

  const setValue = (id, value) => setValues((current) => ({ ...current, [id]: value }))

  const renderField = (field) => {
    if (field.field_type === 'textarea') {
      return <Textarea value={values[field.id] || ''} placeholder={field.placeholder || ''} onChange={(_, data) => setValue(field.id, data.value)} />
    }
    if (field.field_type === 'select') {
      return (
        <Dropdown
          placeholder={field.placeholder || 'Seleccioná una opción'}
          value={values[field.id] || ''}
          selectedOptions={values[field.id] ? [values[field.id]] : []}
          onOptionSelect={(_, data) => setValue(field.id, data.optionValue)}
        >
          {field.options.map((option) => <Option key={option} value={option}>{option}</Option>)}
        </Dropdown>
      )
    }
    if (field.field_type === 'boolean') {
      return <Checkbox checked={Boolean(values[field.id])} onChange={(_, data) => setValue(field.id, data.checked)} label={field.help_text || 'Sí'} />
    }
    return (
      <Input
        type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'}
        value={values[field.id] ?? ''}
        placeholder={field.placeholder || ''}
        onChange={(_, data) => setValue(field.id, field.field_type === 'number' ? (data.value === '' ? '' : Number(data.value)) : data.value)}
      />
    )
  }

  const submit = (event) => {
    event.preventDefault()
    onSubmit(values)
  }

  return (
    <form className="dynamic-form" onSubmit={submit}>
      <div>
        <span className="eyebrow">INFORMACION NECESARIA</span>
        <h3>{form.title}</h3>
        {form.description && <p>{form.description}</p>}
      </div>
      <div className="form-grid">
        {form.fields.map((field) => (
          <Field
            key={field.id}
            label={`${field.label}${field.required ? ' *' : ''}`}
            hint={field.help_text || field.why_needed}
            required={field.required}
          >
            {renderField(field)}
          </Field>
        ))}
      </div>
      <Button appearance="primary" type="submit" disabled={busy}>
        {busy ? 'Procesando...' : submitLabel}
      </Button>
    </form>
  )
}
