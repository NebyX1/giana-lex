import { Accordion, AccordionHeader, AccordionItem, AccordionPanel } from '@fluentui/react-components'

export default function DebugPanel({ debug }) {
  if (!debug || !Object.keys(debug).length) return null
  return (
    <Accordion collapsible className="debug-panel">
      <AccordionItem value="debug">
        <AccordionHeader>Debug de la última operación</AccordionHeader>
        <AccordionPanel>
          <dl>
            <dt>Stage</dt><dd>{debug.stage_before} → {debug.stage_after}</dd>
            <dt>Tools</dt><dd>{debug.tools_executed?.join(', ') || 'Ninguna'}</dd>
            <dt>Examples candidatos</dt><dd>{debug.example_candidates?.map((item) => item.filename).join(', ') || 'Ninguno'}</dd>
            <dt>Examples seleccionados</dt><dd>{debug.examples_selected?.map((item) => item.filename).join(', ') || 'Ninguno'}</dd>
            <dt>LLM requests</dt><dd>{debug.llm?.requests || 0}</dd>
            <dt>Tokens</dt><dd>{debug.llm?.input_tokens || 0} entrada / {debug.llm?.output_tokens || 0} salida / {debug.llm?.total_tokens || 0} total</dd>
            <dt>Duración</dt><dd>{debug.llm?.duration_ms || 0} ms</dd>
          </dl>
        </AccordionPanel>
      </AccordionItem>
    </Accordion>
  )
}
