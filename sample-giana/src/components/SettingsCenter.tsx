import { Button, Card, Select, Text, Title1, Title3 } from '@fluentui/react-components'
import type { Provider, Skill } from '../types'
import { useAppStyles } from '../styles'
import { AppIcon } from './AppIcon'

type Props = {
  providers: Provider[]
  providerId: number
  model: string
  skill: string
  skills: Skill[]
  hasActiveSession: boolean
  isSuperuser: boolean
  onProviderChange: (provider: Provider) => void
  onModelChange: (model: string) => void
  onSkillChange: (skill: string) => void
  onOpenProviders: () => void
  onOpenNationalNorms: () => void
  onOpenDepartmentalNorms: () => void
  onOpenUsers: () => void
  onOpenAuditLog: () => void
  onClose: () => void
}

const providerName = (provider: Provider) => provider.provider === 'ollama' && provider.default_model?.includes('cloud')
  ? 'Ollama Cloud'
  : provider.display_name

type SettingsTileProps = {
  icon: 'book' | 'building' | 'settings' | 'users' | 'history'
  title: string
  description: string
  action: string
  onClick: () => void
}

function SettingsTile({ icon, title, description, action, onClick }: SettingsTileProps) {
  const styles = useAppStyles()

  return <Card className={styles.settingsTile}>
    <div className={styles.settingsTileIcon}><AppIcon name={icon} size={21} /></div>
    <div className={styles.settingsTileCopy}>
      <Text weight="semibold" size={400}>{title}</Text>
      <Text className={styles.muted} size={200}>{description}</Text>
    </div>
    <Button className={styles.settingsTileAction} appearance="secondary" icon={<AppIcon name="chevron" size={14} />} iconPosition="after" onClick={onClick}>{action}</Button>
  </Card>
}

export function SettingsCenter({
  providers,
  providerId,
  model,
  skill,
  skills,
  hasActiveSession,
  isSuperuser,
  onProviderChange,
  onModelChange,
  onSkillChange,
  onOpenProviders,
  onOpenNationalNorms,
  onOpenDepartmentalNorms,
  onOpenUsers,
  onOpenAuditLog,
  onClose,
}: Props) {
  const styles = useAppStyles()
  const selectedProvider = providers.find((provider) => provider.id === providerId)

  return <main className={styles.settingsPage}>
    <header className={styles.settingsHero}>
      <Button className={styles.managerBackButton} appearance="secondary" size="large" icon={<AppIcon name="arrow-left" />} onClick={onClose}>Volver al espacio de trabajo</Button>
      <div className={styles.settingsHeroHeading}>
        <div className={styles.settingsHeroIcon}><AppIcon name="settings" size={26} /></div>
        <div>
          <Text className={styles.managerEyebrow} size={100} weight="semibold" block>CONFIGURACIÓN</Text>
          <Title1>Centro de configuración</Title1>
          <Text className={styles.muted} block>Modelos, fuentes jurídicas y accesos administrativos en un único lugar.</Text>
        </div>
      </div>
    </header>

    <section className={styles.settingsSection} aria-labelledby="agent-settings-title">
      <div className={styles.settingsSectionHeader}>
        <div>
          <Title3 id="agent-settings-title">Modelo y comportamiento del agente</Title3>
          <Text className={styles.muted} size={200} block>Defina cómo se atenderán las nuevas consultas jurídicas.</Text>
        </div>
        {hasActiveSession && <Text className={styles.settingsLockNotice} size={200}><AppIcon name="shield" size={14} /> Proveedor y modelo fijados para esta conversación</Text>}
      </div>
      <Card className={styles.settingsModelCard}>
        <label className={styles.settingsField}>
          <span>Proveedor de IA</span>
          <Select aria-label="Proveedor de IA" value={String(providerId)} disabled={hasActiveSession} onChange={(_, data) => {
            const provider = providers.find((item) => item.id === Number(data.value))
            if (provider) onProviderChange(provider)
          }}>
            <option value="0">Seleccionar proveedor</option>
            {providers.map((provider) => <option value={provider.id} key={provider.id}>{providerName(provider)}</option>)}
          </Select>
          <small>{hasActiveSession ? 'Disponible al iniciar una nueva consulta.' : 'Conexión que ejecutará el agente.'}</small>
        </label>
        <label className={styles.settingsField}>
          <span>Modelo</span>
          <Select aria-label="Modelo" value={model} disabled={hasActiveSession || !selectedProvider} onChange={(_, data) => onModelChange(data.value)}>
            {!model && <option value="">Modelo predeterminado</option>}
            {model && model !== selectedProvider?.default_model && <option value={model}>{model}</option>}
            {selectedProvider?.default_model && <option value={selectedProvider.default_model}>{selectedProvider.default_model}</option>}
          </Select>
          <small>{hasActiveSession ? 'Se conserva para asegurar continuidad.' : 'Modelo predeterminado del proveedor.'}</small>
        </label>
        <label className={styles.settingsField}>
          <span>Especialidad</span>
          <Select aria-label="Especialidad" value={skill} onChange={(_, data) => onSkillChange(data.value)}>
            <option value="automatic">Enrutamiento automático</option>
            {skills.map((item) => <option key={item.name} value={item.name}>{item.name.replaceAll('-', ' ')}</option>)}
          </Select>
          <small>Puede ajustarse antes de cada intervención.</small>
        </label>
      </Card>
    </section>

    <section className={styles.settingsSection} aria-labelledby="library-settings-title">
      <div className={styles.settingsSectionHeader}>
        <div>
          <Title3 id="library-settings-title">Biblioteca jurídica</Title3>
          <Text className={styles.muted} size={200} block>Administre el corpus que el agente consulta y cita.</Text>
        </div>
      </div>
      <div className={styles.settingsGrid}>
        <SettingsTile icon="book" title="Normativa nacional" description="Fuentes oficiales, indexación y actualización desde IMPO." action="Administrar" onClick={onOpenNationalNorms} />
        <SettingsTile icon="building" title="Normativa departamental" description="Digesto de Lavalleja, textos utilizables y materias." action="Administrar" onClick={onOpenDepartmentalNorms} />
      </div>
    </section>

    <section className={styles.settingsSection} aria-labelledby="admin-settings-title">
      <div className={styles.settingsSectionHeader}>
        <div>
          <Title3 id="admin-settings-title">Administración</Title3>
          <Text className={styles.muted} size={200} block>Conexiones externas y controles de acceso del sistema.</Text>
        </div>
      </div>
      <div className={styles.settingsGrid}>
        <SettingsTile icon="settings" title="Proveedores de IA" description="Credenciales, endpoints cloud y modelos disponibles." action="Configurar" onClick={onOpenProviders} />
        {isSuperuser && <SettingsTile icon="users" title="Usuarios y permisos" description="Altas, estado de cuentas y funciones administrativas." action="Administrar" onClick={onOpenUsers} />}
        {isSuperuser && <SettingsTile icon="history" title="Registro de actividad" description="Auditoría de archivados, restauraciones, eliminaciones y accesos administrativos." action="Consultar" onClick={onOpenAuditLog} />}
      </div>
    </section>
  </main>
}
