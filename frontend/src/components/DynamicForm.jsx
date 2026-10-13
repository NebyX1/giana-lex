import { useEffect, useState } from 'react'
import {
  Button,
  Checkbox,
  Field,
  Input,
  Textarea,
} from '@fluentui/react-components'

export default function DynamicForm({ form, onSubmit, busy, submitLabel = 'Continuar', disabled = false, initialValues = {} }) {
  const [values, setValues] = useState({})

  useEffect(() => {
    const defaults = Object.fromEntries(form.fields.filter((field) => field.field_type === 'boolean').map((field) => [field.id, false]))
    setValues({ ...defaults, ...initialValues })
  }, [form, disabled])

  const setValue = (id, value) => setValues((current) => ({ ...current, [id]: value }))

  const renderField = (field) => {
    if (field.field_type === 'textarea') {
      return <Textarea disabled={disabled} value={values[field.id] || ''} placeholder={field.placeholder || ''} onChange={(_, data) => setValue(field.id, data.value)} />
    }
    if (field.field_type === 'select') {
      return (
        <select
          value={values[field.id] || ''}
          required={!disabled && field.required}
          disabled={disabled}
          onChange={(event) => setValue(field.id, event.target.value)}
        >
          <option value="" disabled>{field.placeholder || 'Seleccioná una opción'}</option>
          {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      )
    }
    if (field.field_type === 'boolean') {
      return <Checkbox disabled={disabled} checked={Boolean(values[field.id])} onChange={(_, data) => setValue(field.id, data.checked)} label={field.help_text || 'Sí'} />
    }
    return (
      <Input
        type={field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'}
        value={values[field.id] ?? ''}
        disabled={disabled}
        placeholder={field.placeholder || ''}
        onChange={(_, data) => setValue(field.id, field.field_type === 'number' ? (data.value === '' ? '' : Number(data.value)) : data.value)}
      />
    )
  }

  const submit = (event) => {
    event.preventDefault()
    if (!disabled) onSubmit(values)
  }

  return (
    <form className={`dynamic-form ${disabled ? 'completed' : ''}`} onSubmit={submit}>
      <div>
        <span className="eyebrow">{disabled ? 'INFORMACIÓN ENVIADA' : 'INFORMACION NECESARIA'}</span>
        <h3>{form.title}</h3>
        {form.description && <p>{form.description}</p>}
      </div>
      <div className="form-grid">
        {form.fields.map((field) => (
          <Field
            key={field.id}
            label={`${field.label}${field.required ? ' *' : ''}`}
            hint={field.help_text || field.why_needed}
            required={!disabled && field.required}
          >
            {renderField(field)}
          </Field>
        ))}
      </div>
      <Button appearance={disabled ? 'secondary' : 'primary'} type="submit" disabled={disabled || busy}>
        {disabled ? 'Formulario enviado' : busy ? 'Procesando...' : submitLabel}
      </Button>
    </form>
  )
}
