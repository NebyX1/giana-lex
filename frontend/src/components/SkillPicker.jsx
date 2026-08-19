import { Button } from '@fluentui/react-components'
import { DocumentArrowDownRegular, ShieldCheckmarkRegular } from '@fluentui/react-icons'

export default function SkillPicker({ skills, onRun, onExport, busy }) {
  return (
    <section className="skill-picker">
      <span className="eyebrow">ANALISIS ADICIONALES</span>
      <h3>Borrador aprobado</h3>
      <p>Podés ejecutar análisis independientes o exportar el documento.</p>
      <div className="skill-list">
        {skills.map((skill) => (
          <div className="skill-card" key={skill.key}>
            <ShieldCheckmarkRegular />
            <div><strong>{skill.name}</strong><p>{skill.description}</p></div>
            <Button disabled={busy === `skill-${skill.key}`} onClick={() => onRun(skill.key)}>
              {busy === `skill-${skill.key}` ? 'Analizando...' : 'Ejecutar'}
            </Button>
          </div>
        ))}
      </div>
      <Button appearance="primary" icon={<DocumentArrowDownRegular />} onClick={onExport}>Exportar Word</Button>
    </section>
  )
}
