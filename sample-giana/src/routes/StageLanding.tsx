import { Text, Title1 } from '@fluentui/react-components'
import { Link } from 'react-router-dom'
import { AppIcon } from '../components/AppIcon'
import { LegalLayout } from '../features/cases/CaseListPage'

export function StageLanding({ title }: { title: string }) {
  return <LegalLayout><div className="legal-empty"><AppIcon name="document" size={30} /><Title1 as="h1">{title}</Title1><Text className="legal-muted">Seleccione un expediente para abrir esta etapa con sus datos persistidos.</Text><Link className="legal-primary-link" to="/cases">Ver expedientes</Link></div></LegalLayout>
}
