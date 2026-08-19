import DynamicForm from './DynamicForm.jsx'

const riskLabels = { low: 'Bajo', medium: 'Medio', high: 'Alto', unknown: 'No determinado' }

export default function SkillResult({ skill, result, onSubmit, busy }) {
  return (
    <section className="skill-result">
      <div className="result-title"><h3>{skill?.name || 'Análisis'}</h3><span>{riskLabels[result.overall_risk]}</span></div>
      <p>{result.summary}</p>
      {result.findings.map((finding, index) => (
        <article key={`${finding.title}-${index}`}>
          <strong>{finding.title}</strong>
          <small>{riskLabels[finding.risk_level]}</small>
          <p>{finding.explanation}</p>
          {finding.affected_actors.length > 0 && <p>Actores: {finding.affected_actors.join(', ')}</p>}
          {finding.mitigation && <p>Mitigación: {finding.mitigation}</p>}
        </article>
      ))}
      {result.status === 'needs_input' && result.questions && (
        <DynamicForm form={result.questions} onSubmit={onSubmit} busy={busy} submitLabel="Completar análisis" />
      )}
    </section>
  )
}
