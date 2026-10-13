import { useEffect, useState } from 'react'
import { Button, Text, Textarea } from '@fluentui/react-components'
import { CheckmarkRegular, EditRegular } from '@fluentui/react-icons'

export default function DraftPanel({ draft, approved, verification, onRevise, onApprove, onCheck, busy }) {
  const [editing, setEditing] = useState(false)
  const [instructions, setInstructions] = useState('')
  const [workingDraft, setWorkingDraft] = useState(draft)
  const [editingText, setEditingText] = useState(false)
  useEffect(() => { setWorkingDraft(draft); setEditingText(false) }, [draft])
  const critical = verification?.findings?.some((item) => item.severity === 'critical' && !item.resolved)

  const submitRevision = async () => {
    try {
      await onRevise(instructions)
      setInstructions('')
      setEditing(false)
    } catch {
      // The parent keeps the global error visible and the instructions intact.
    }
  }

  return (
    <div className="draft-panel">
      <div className="draft-heading">
        <span className="eyebrow">BORRADOR</span>
        <span className={`status ${approved ? 'approved' : ''}`}>{approved ? 'APROBADO' : 'EN REVISION'}</span>
      </div>
      {editingText ? <Textarea className="draft-text-editor" value={workingDraft} onChange={(_, data) => setWorkingDraft(data.value)} aria-label="Texto del borrador para comprobar" /> : <pre>{draft}</pre>}
      {!approved && <section className="verification-panel"><div className="example-actions"><Button onClick={() => setEditingText((value) => !value)} disabled={Boolean(busy)}>{editingText ? 'Cerrar edición' : 'Editar texto'}</Button><Button appearance="primary" disabled={Boolean(busy) || !workingDraft.trim()} onClick={() => onCheck(workingDraft)}>{busy === 'check' ? 'Comprobando...' : 'Comprobar borrador'}</Button></div>{verification ? <><strong>{verification.summary}</strong><Text size={200}>Cobertura: {verification.coverage.join(', ')}. Normativa: {verification.normative_status?.content === 'not_checked' ? 'sin texto normativo comprobado' : verification.normative_status?.content}.</Text>{verification.findings.map((finding) => <details key={finding.id}><summary>{finding.severity === 'critical' ? 'Crítico' : 'Revisar'} · {finding.category} · {finding.location}</summary><p>{finding.explanation}</p><p>Acción: {finding.action}</p><small>{finding.evidence?.map((e) => e.excerpt).join(' · ')}</small></details>)}{verification.examples?.length > 0 && <details><summary>{verification.examples.length} referencias editoriales utilizadas</summary>{verification.examples.map((item) => <p key={item.id}>{item.title} · {item.scope} · {item.match_class}: {item.reasons?.join('; ')}</p>)}</details>}</> : <Text size={200}>Compruebe esta revisión antes de aprobar.</Text>}</section>}
      {!approved && (
        <div className="draft-actions">
          {editing ? (
            <div className="revision-box">
              <Textarea
                value={instructions}
                onChange={(_, data) => setInstructions(data.value)}
                placeholder="¿Qué querés modificar?"
                aria-label="Modificaciones"
              />
              <Button appearance="primary" disabled={!instructions.trim() || busy === 'revise'} onClick={submitRevision}>
                {busy === 'revise' ? 'Aplicando...' : 'Aplicar modificaciones'}
              </Button>
              <Button appearance="subtle" onClick={() => setEditing(false)}>Cancelar</Button>
            </div>
          ) : (
            <>
              <Button icon={<EditRegular />} disabled={Boolean(busy)} onClick={() => setEditing(true)}>Solicitar modificaciones</Button>
              <Button appearance="primary" icon={<CheckmarkRegular />} disabled={Boolean(busy) || !verification || critical || workingDraft !== draft} onClick={onApprove}>
                {busy === 'approve' ? 'Aprobando...' : 'Aprobar borrador'}
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
