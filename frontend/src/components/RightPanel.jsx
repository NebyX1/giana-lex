import { useState } from 'react'
import { Button, Card, Text } from '@fluentui/react-components'
import { BookRegular, DismissRegular, DocumentTextRegular, OpenRegular } from '@fluentui/react-icons'
import DraftPanel from './DraftPanel.jsx'

export default function RightPanel({ conversation, busy, onRevise, onApprove, onClose }) {
  const [tab, setTab] = useState(conversation?.draft ? 'draft' : 'sources')
  const sources = conversation?.examples || []

  return (
    <aside className="right-panel" aria-label="Panel de trabajo">
      <div className="panel-header"><div><Text weight="semibold" size={400} block>Panel de trabajo</Text><div className="panel-status"><span /> Sincronizado</div></div><Button className="panel-close" appearance="subtle" icon={<DismissRegular />} aria-label="Cerrar panel" onClick={onClose} /></div>
      <div className="panel-tabs">
        <Button appearance="subtle" data-active={tab === 'sources'} icon={<BookRegular />} onClick={() => setTab('sources')}>Antecedentes</Button>
        <Button appearance="subtle" data-active={tab === 'draft'} icon={<DocumentTextRegular />} onClick={() => setTab('draft')}>Borrador</Button>
      </div>
      {tab === 'sources' ? <div className="panel-body">
        {sources.length ? sources.map((source, index) => <Card className="source-card" key={source.filename || index}>
          <div className="source-heading"><span>{index + 1}</span><div><Text weight="semibold" block>{source.filename}</Text><Text size={200} className="muted">Antecedente {source.relevance === 'strong' ? 'de alta relevancia' : 'de relevancia parcial'}</Text></div></div>
          <Text className="source-excerpt">{source.reason || 'Seleccionado por similitud con la consulta actual.'}</Text>
          <Button appearance="subtle" size="small" icon={<OpenRegular />}>Referencia interna</Button>
        </Card>) : <div className="panel-placeholder"><div><BookRegular /></div><Text weight="semibold">Antecedentes de la consulta</Text><Text className="muted">Las referencias seleccionadas por el backend aparecerán aquí al iniciar una consulta.</Text></div>}
      </div> : conversation?.draft ? <DraftPanel draft={conversation.draft} approved={conversation.approved} onRevise={onRevise} onApprove={onApprove} busy={busy} /> : <div className="panel-placeholder"><div><DocumentTextRegular /></div><Text weight="semibold">Borrador en preparación</Text><Text className="muted">Complete la información solicitada para generar el documento.</Text></div>}
    </aside>
  )
}
