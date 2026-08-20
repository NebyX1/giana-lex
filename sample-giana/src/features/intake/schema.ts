export type FieldType = 'text' | 'textarea' | 'date' | 'number' | 'currency' | 'select' | 'multiselect' | 'boolean' | 'document_reference' | 'person_table' | 'budget_table' | 'budget_transfer_table'

export type DocumentType =
  | 'expediente' | 'informe_hacienda' | 'informe_contaduria' | 'oficio' | 'resolucion'
  | 'decreto' | 'anexo_presupuestal' | 'other' | 'oficio_contaduria' | 'contrato'
  | 'informe_presupuestal' | 'informe_tecnico' | 'procedimiento_contratacion' | 'anexo' | 'otro'

export type DocumentReferenceValue = {
  document_type: DocumentType | ''
  number?: string
  year?: number | string
  date?: string
  issuer?: string
  upload_id?: number
  source_document_id?: number
  source_url?: string
  notes?: string
  title?: string
}

export type BudgetAllocationComponent = 'identifier' | 'program' | 'project' | 'object' | 'auxiliary' | 'financing' | 'unit'
export type BudgetAllocationValue = Partial<Record<BudgetAllocationComponent, string>>
export type BudgetTransferValue = { origin: BudgetAllocationValue; destination: BudgetAllocationValue; amount: string }
export type LegacyTableValue = Array<Record<string, string>>
export type FormValue = string | boolean | string[] | LegacyTableValue | DocumentReferenceValue | DocumentReferenceValue[] | BudgetTransferValue[] | null

export type FieldProvenanceDefinition = {
  field_key: string
  source_type: 'workflow' | 'validated_precedent_structure' | 'user_message' | 'persisted_fact' | 'uploaded_document' | 'user_answer' | string
  source_ref?: string | null
  reason: string
  requires_confirmation: boolean
  value?: unknown
}

export type FieldValidationRules = {
  min?: number
  max?: number
  min_length?: number
  pattern?: string
  integer?: boolean
  multiple?: boolean
  document_type?: DocumentType
  issuer_contains?: string[]
  issuer_help?: string
  allocation_components?: BudgetAllocationComponent[]
  min_rows?: number
  after?: string
}

export type FormFieldDefinition = {
  key: string
  label: string
  field_type: FieldType
  required?: boolean
  origin?: string
  reason?: string
  validation_rules?: FieldValidationRules
  visible_when?: { field: string; equals: unknown }
  prefilled_value?: unknown
  provenance?: FieldProvenanceDefinition
  confidence?: number | null
  options?: Array<string | { label: string; value: string }>
}

export type FormSection = { id: string; title: string; description?: string; fields: FormFieldDefinition[] }
export type IntakeSchema = { id?: string; version?: number; title?: string; description?: string; sections: FormSection[] }
