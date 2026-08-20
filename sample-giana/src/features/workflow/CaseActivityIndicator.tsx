import { useEffect, useState } from 'react'
import { Badge, Button, MessageBar, MessageBarBody, Spinner, Text } from '@fluentui/react-components'
import type { CaseWorkspaceData } from '../../api/legal'
import { activityLabel, CASE_STAGES, caseProgress } from './caseProgress'

const WATCHDOG_MS = 120_000

function elapsed(startedAt: string | null | undefined, now: number) {
  if (!startedAt) return ''
  const milliseconds = Math.max(0, now - new Date(startedAt).getTime())
  const minutes = Math.floor(milliseconds / 60_000)
  const seconds = Math.floor(milliseconds % 60_000 / 1_000)
  return minutes ? `${minutes} min ${seconds} s` : `${seconds} s`
}

export function CaseActivityIndicator({ workspace, streamError, onRefresh }: { workspace: CaseWorkspaceData; streamError?: string; onRefresh: () => Promise<unknown> }) {
  const [now, setNow] = useState(Date.now())
  const [refreshing, setRefreshing] = useState(false)
  const activity = workspace.activity

  useEffect(() => {
    if (activity.kind !== 'working') return
    const timer = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [activity.kind])

  const elapsedText = elapsed(activity.started_at, now)
  const lastActivity = activity.updated_at ?? activity.started_at
  const watchdog = activity.kind === 'working' && lastActivity
    ? now - new Date(lastActivity).getTime() >= WATCHDOG_MS
    : false
  const color = activity.kind === 'failed' || activity.kind === 'blocked' ? 'danger'
    : activity.kind === 'completed' ? 'success'
      : activity.kind === 'waiting_user' || activity.kind === 'waiting_human_review' ? 'warning'
        : 'informative'
  const currentStage = CASE_STAGES[caseProgress(workspace).findIndex((status) => status === 'current')] ?? 'Procesamiento jurídico'

  async function refresh() {
    setRefreshing(true)
    try { await onRefresh() } finally { setRefreshing(false) }
  }

  return <div className="case-activity" data-kind={activity.kind} aria-live="polite">
    <div className="case-activity-main">
      {activity.kind === 'working' && <Spinner size="tiny" />}
      <Badge appearance="tint" color={color}>{activity.kind.replaceAll('_', ' ')}</Badge>
      <div><Text weight="semibold" block>{activity.kind === 'working' ? 'Giana está trabajando' : activity.kind === 'waiting_human_review' ? 'Automatización finalizada' : activityLabel(workspace)}</Text>{activity.kind === 'working' && <Text className="legal-muted" size={200}>Etapa: {currentStage}</Text>}{activity.kind === 'waiting_human_review' && <Text className="legal-muted" size={200}>Esperando revisión humana</Text>}</div>
      {elapsedText && <Text className="legal-muted">{elapsedText}</Text>}
      <Button size="small" appearance="subtle" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? <Spinner size="tiny" /> : 'Actualizar'}</Button>
    </div>
    {(streamError || watchdog) && <MessageBar intent="warning"><MessageBarBody>{streamError || 'Este paso está tardando más de lo esperado. Actualice para comprobar el estado persistido.'}</MessageBarBody></MessageBar>}
  </div>
}
