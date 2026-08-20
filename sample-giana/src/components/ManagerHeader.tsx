import type { ReactNode } from 'react'
import { Button, Text, Title2 } from '@fluentui/react-components'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'

type Props = {
  eyebrow: string
  title: string
  description: string
  onBack?: () => void
  actions?: ReactNode
}

export function ManagerHeader({ eyebrow, title, description, onBack, actions }: Props) {
  const styles = useAppStyles()

  return <header className={styles.managerHeader}>
    {onBack && <Button className={styles.managerBackButton} appearance="secondary" size="large" icon={<AppIcon name="arrow-left" />} onClick={onBack}>Volver a configuración</Button>}
    <div className={styles.managerTitleRow}>
      <div>
        <Text className={styles.managerEyebrow} size={100} weight="semibold" block>{eyebrow}</Text>
        <Title2>{title}</Title2>
        <Text className={styles.muted} block>{description}</Text>
      </div>
      {actions && <div className={styles.managerHeaderActions}>{actions}</div>}
    </div>
  </header>
}
