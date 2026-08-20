import { useCallback, useEffect, useRef, useState } from 'react'
import { legalApi, streamCaseEvents, type CaseEvent, type CaseWorkspaceData, type HumanReviewFindingInput } from '../../api/legal'

type InFlightRequest = { caseId: string; promise: Promise<CaseWorkspaceData> }

export function useCaseWorkspace(caseId: string) {
  const [workspace, setWorkspace] = useState<CaseWorkspaceData>()
  const [events, setEvents] = useState<CaseEvent[]>([])
  const [loading, setLoading] = useState(Boolean(caseId))
  const [streamError, setStreamError] = useState('')
  const [error, setError] = useState('')
  const [cursor, setCursor] = useState(0)
  const [lastEventAt, setLastEventAt] = useState<string>()
  const activeCase = useRef(caseId)
  const requestVersion = useRef(0)
  const appliedVersion = useRef(0)
  const inFlight = useRef<InFlightRequest | undefined>(undefined)
  const streamController = useRef<AbortController | undefined>(undefined)

  activeCase.current = caseId

  const loadWorkspace = useCallback((force = false) => {
    if (!caseId) return Promise.reject(new Error('No hay un expediente vinculado.'))
    if (!force && inFlight.current?.caseId === caseId) return inFlight.current.promise

    const version = ++requestVersion.current
    const promise = legalApi.workspace(caseId).then((response) => {
      if (activeCase.current === caseId && version >= appliedVersion.current) {
        appliedVersion.current = version
        setWorkspace(response)
        setCursor((value) => Math.max(value, response.activity.last_event_sequence ?? response.snapshot.last_sequence_number ?? 0))
        setLastEventAt(response.activity.updated_at ?? response.snapshot.updated_at ?? undefined)
        setError('')
      }
      return response
    }).finally(() => {
      if (inFlight.current?.promise === promise) inFlight.current = undefined
    })
    inFlight.current = { caseId, promise }
    return promise
  }, [caseId])

  const refresh = useCallback(() => loadWorkspace(), [loadWorkspace])

  useEffect(() => {
    setWorkspace(undefined)
    setEvents([])
    setCursor(0)
    setLastEventAt(undefined)
    setError('')
    setStreamError('')
    appliedVersion.current = 0
    requestVersion.current += 1
    inFlight.current = undefined
    streamController.current?.abort()
    if (!caseId) {
      setLoading(false)
      return
    }

    const controller = new AbortController()
    streamController.current = controller
    setLoading(true)
    void refresh().then((initial) => {
      if (controller.signal.aborted || activeCase.current !== caseId) return
      setLoading(false)
      return streamCaseEvents(caseId, {
        signal: controller.signal,
        after: initial.activity.last_event_sequence ?? initial.snapshot.last_sequence_number,
        onEvent: (event) => {
          if (activeCase.current !== caseId) return
          setCursor((value) => Math.max(value, event.sequence_number))
          setLastEventAt((value) => !value || new Date(event.occurred_at).getTime() > new Date(value).getTime() ? event.occurred_at : value)
          setEvents((current) => current.some((item) => item.sequence_number === event.sequence_number) ? current : [...current, event])
          void refresh().catch(() => undefined)
        },
        onReconnect: async () => {
          await refresh()
          if (activeCase.current === caseId) setStreamError('')
        },
        onError: () => {
          if (activeCase.current === caseId) setStreamError('Reconectando el canal de actividad...')
        },
      })
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted && activeCase.current === caseId) {
        setError(caught instanceof Error ? caught.message : 'No se pudo cargar el expediente.')
        setLoading(false)
      }
    })

    return () => {
      controller.abort()
      if (streamController.current === controller) streamController.current = undefined
    }
  }, [caseId, refresh])

  const submitForm = useCallback(async (formId: string, answers: Record<string, unknown>, partial = false) => {
    await legalApi.submitForm(caseId, formId, answers, partial)
    return loadWorkspace(true)
  }, [caseId, loadWorkspace])

  const confirmFacts = useCallback(async (factIds: string[]) => {
    await legalApi.confirmFacts(caseId, factIds)
    return loadWorkspace(true)
  }, [caseId, loadWorkspace])

  const cancel = useCallback(async (reason?: string) => {
    await legalApi.cancel(caseId, reason)
    return loadWorkspace(true)
  }, [caseId, loadWorkspace])

  const retry = useCallback(async () => {
    await legalApi.retry(caseId)
    return loadWorkspace(true)
  }, [caseId, loadWorkspace])

  const start = useCallback(async () => {
    await legalApi.start(caseId)
    return loadWorkspace(true)
  }, [caseId, loadWorkspace])

  const review = useCallback(async (approved: boolean, findings: HumanReviewFindingInput[]) => {
    if (!workspace?.draft) throw new Error('No hay un borrador persistido para revisar.')
    await legalApi.review(caseId, approved, findings, workspace.draft)
    return loadWorkspace(true)
  }, [caseId, loadWorkspace, workspace?.draft])

  return {
    legalCase: workspace?.case,
    snapshot: workspace?.snapshot,
    activity: workspace?.activity,
    workspace,
    events,
    loading,
    error,
    streamError,
    cursor,
    lastEventAt,
    refresh,
    start,
    retry,
    cancel,
    submitForm,
    confirmFacts,
    review,
    stopStream: () => streamController.current?.abort(),
  }
}

export type CaseWorkspaceController = ReturnType<typeof useCaseWorkspace>
