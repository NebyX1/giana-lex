import { useState } from 'react'
import { Button, Textarea } from '@fluentui/react-components'
import { CheckmarkRegular, EditRegular } from '@fluentui/react-icons'

export default function DraftPanel({ draft, approved, onRevise, onApprove, busy }) {
  const [editing, setEditing] = useState(false)
  const [instructions, setInstructions] = useState('')

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
      <pre>{draft}</pre>
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
              <Button appearance="primary" icon={<CheckmarkRegular />} disabled={busy === 'approve'} onClick={onApprove}>
                {busy === 'approve' ? 'Aprobando...' : 'Aprobar borrador'}
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
