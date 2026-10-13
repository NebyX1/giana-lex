import { useState } from 'react'
import { Button, Card, Text } from '@fluentui/react-components'
import { BookRegular, DismissRegular, DocumentTextRegular, OpenRegular } from '@fluentui/react-icons'
import DraftPanel from './DraftPanel.jsx'

export default function RightPanel({ conversation, busy, onRevise, onApprove, onCheck, onClose }) {
  const [tab, setTab] = useState(conversation?.draft ? 'draft' : 'sources')
  const editorial = (conversation?.example_references || []).map((source) => ({
    key: `editorial-${source.id}`, title: source.title, subtitle: `${source.match_class} · ${source.scope}`,
    excerpt: `${(source.reasons || []).join('; ')}${source.defectos_detectados?.length ? ' · Advertencias: ' + source.defectos_detectados[0] : ''}`,
    url: source.url,
  }))
  const official = (conversation?.official_references || []).map((source) => ({
    key: `official-${source.resolution_id}`,
    title: `Resolución N° ${source.number}`,
    subtitle: `${source.role === 'canonical' ? 'Antecedente canónico' : source.role === 'secondary' ? 'Antecedente secundario' : 'Antecedente relacionado'}`,
    excerpt: source.title,
    url: source.source_url,
  }))
  const selected = (conversation?.examples || []).map((source) => ({
    key: `selected-${source.filename}`,
    title: source.filename,
    subtitle: source.relevance === 'strong' ? 'Antecedente de alta relevancia' : 'Antecedente de relevancia parcial',
    excerpt: source.reason || 'Seleccionado para esta consulta.',
  }))
  const knownFiles = new Set(selected.map((source) => source.title))
  const consulted = (conversation?.debug?.example_candidates || []).filter((source) => !knownFiles.has(source.filename)).map((source) => ({
    key: `consulted-${source.filename}`,
    title: source.title || source.filename,
    subtitle: 'Documento consultado',
    excerpt: source.excerpt || 'Evaluado durante la búsqueda de antecedentes.',
  }))
  const sources = [...editorial, ...official, ...selected.filter((source) => !source.title.startsWith('catalog:')), ...consulted.filter((source) => !source.title.startsWith('catalog:'))]

  return (
    <aside className="right-panel" aria-label="Panel de trabajo">
      <div className="panel-header"><div><Text weight="semibold" size={400} block>Panel de trabajo</Text><div className="panel-status"><span /> Sincronizado</div></div><Button className="panel-close" appearance="subtle" icon={<DismissRegular />} aria-label="Cerrar panel" onClick={onClose} /></div>
      <div className="panel-tabs">
        <Button appearance="subtle" data-active={tab === 'sources'} icon={<BookRegular />} onClick={() => setTab('sources')}>Antecedentes</Button>
        <Button appearance="subtle" data-active={tab === 'draft'} icon={<DocumentTextRegular />} onClick={() => setTab('draft')}>Borrador</Button>
      </div>
      {tab === 'sources' ? <div className="panel-body">
        {sources.length ? sources.map((source, index) => <Card className="source-card" key={source.key || index}>
          <div className="source-heading"><span>{index + 1}</span><div><Text weight="semibold" block>{source.title}</Text><Text size={200} className="muted">{source.subtitle}</Text></div></div>
          <Text className="source-excerpt">{source.excerpt}</Text>
          {source.url ? <Button as="a" href={source.url} target="_blank" rel="noopener noreferrer" appearance="subtle" size="small" icon={<OpenRegular />}>Abrir fuente oficial</Button> : <Button appearance="subtle" size="small" icon={<OpenRegular />} disabled>Referencia interna</Button>}
        </Card>) : <div className="panel-placeholder"><div><BookRegular /></div><Text weight="semibold">Antecedentes de la consulta</Text><Text className="muted">Las referencias seleccionadas por el backend aparecerán aquí al iniciar una consulta.</Text></div>}
      </div> : conversation?.draft ? <DraftPanel draft={conversation.draft} approved={conversation.approved} verification={conversation.verification} onRevise={onRevise} onApprove={onApprove} onCheck={onCheck} busy={busy} /> : <div className="panel-placeholder"><div><DocumentTextRegular /></div><Text weight="semibold">Borrador en preparación</Text><Text className="muted">Complete la información solicitada para generar el documento.</Text></div>}
    </aside>
  )
}
