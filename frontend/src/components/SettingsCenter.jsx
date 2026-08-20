import { Button, Card, Select, Text, Title1, Title3 } from '@fluentui/react-components'
import { ArrowLeftRegular, BookRegular, BotRegular, BuildingRegular, ChevronRightRegular, HistoryRegular, PeopleRegular, SettingsRegular, ShieldLockRegular } from '@fluentui/react-icons'

const tiles = [
  { view: 'knowledge', icon: BookRegular, title: 'Conocimiento jurídico', description: 'Tipologías, resoluciones oficiales y estado del índice semántico.', action: 'Abrir biblioteca' },
  { view: 'national', icon: BookRegular, title: 'Normativa nacional', description: 'Fuentes oficiales, indexación y actualización desde IMPO.', action: 'Administrar' },
  { view: 'departmental', icon: BuildingRegular, title: 'Normativa departamental', description: 'Digesto de Lavalleja, textos utilizables y materias.', action: 'Administrar' },
  { view: 'providers', icon: BotRegular, title: 'Proveedores de IA', description: 'Credenciales, endpoints cloud y modelos disponibles.', action: 'Configurar' },
  { view: 'users', icon: PeopleRegular, title: 'Usuarios y permisos', description: 'Altas, estado de cuentas y funciones administrativas.', action: 'Administrar' },
  { view: 'audit', icon: HistoryRegular, title: 'Registro de actividad', description: 'Trazabilidad de accesos y acciones sensibles.', action: 'Consultar' },
]

function SettingsTile({ tile, onNavigate }) {
  const Icon = tile.icon
  return <Card className="settings-tile"><div className="settings-tile-icon"><Icon /></div><div><Text weight="semibold" size={400} block>{tile.title}</Text><Text className="muted" size={200}>{tile.description}</Text></div><Button appearance="secondary" icon={<ChevronRightRegular />} iconPosition="after" onClick={() => onNavigate(tile.view)}>{tile.action}</Button></Card>
}

export default function SettingsCenter({ hasConversation, skills, onNavigate, onClose }) {
  return <main className="standalone-page settings-page">
    <header className="settings-hero"><Button className="back-button" appearance="secondary" size="large" icon={<ArrowLeftRegular />} onClick={onClose}>Volver al espacio de trabajo</Button><div className="settings-heading"><div className="settings-hero-icon"><SettingsRegular /></div><div><Text className="manager-eyebrow" size={100} weight="semibold" block>CONFIGURACIÓN</Text><Title1>Centro de configuración</Title1><Text className="muted">Modelos, fuentes jurídicas y accesos administrativos en un único lugar.</Text></div></div></header>
    <section className="settings-section"><div className="settings-section-header"><div><Title3>Modelo y comportamiento del agente</Title3><Text className="muted" size={200}>Defina cómo se atenderán las nuevas consultas jurídicas.</Text></div>{hasConversation && <Text className="lock-notice" size={200}><ShieldLockRegular /> Proveedor y modelo fijados para esta conversación</Text>}</div><Card className="model-card">
      <label><span>Proveedor de IA</span><Select disabled={hasConversation} defaultValue="actual"><option value="actual">Backend actual</option></Select><small>La conexión continúa administrada por la configuración existente del backend.</small></label>
      <label><span>Modelo</span><Select disabled={hasConversation} defaultValue="default"><option value="default">Modelo predeterminado</option></Select><small>Se conserva para asegurar continuidad del workflow.</small></label>
      <label><span>Especialidad</span><Select defaultValue="automatic"><option value="automatic">Enrutamiento automático</option>{skills.map((skill) => <option key={skill.key} value={skill.key}>{skill.name}</option>)}</Select><small>Las capacidades disponibles son informadas por el backend.</small></label>
    </Card></section>
    <section className="settings-section"><div className="settings-section-header"><div><Title3>Biblioteca jurídica</Title3><Text className="muted" size={200}>Administre el conocimiento persistente utilizado por el agente.</Text></div></div><div className="settings-grid">{tiles.slice(0, 3).map((tile) => <SettingsTile key={tile.view} tile={tile} onNavigate={onNavigate} />)}</div></section>
    <section className="settings-section"><div className="settings-section-header"><div><Title3>Administración</Title3><Text className="muted" size={200}>Conexiones externas y controles de acceso del sistema.</Text></div></div><div className="settings-grid">{tiles.slice(3).map((tile) => <SettingsTile key={tile.view} tile={tile} onNavigate={onNavigate} />)}</div></section>
  </main>
}
