export type User = { id: number; email: string; display_name: string; is_superuser?: boolean; is_active?: boolean }

export type Provider = {
  id: number
  provider: 'openai' | 'featherless' | 'ollama' | 'custom'
  display_name: string
  auth_mode: string
  base_url: string
  default_model: string | null
  has_credentials: boolean
}

export type Message = {
  id?: number
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  created_at?: string
}

export type ToolActivity = {
  callId: string
  name: string
  status: 'running' | 'completed' | 'failed' | 'waiting' | 'skipped'
  detail?: string
}

export type Question = {
  id: string
  type: 'text' | 'single_choice' | 'multiple_choice' | 'confirmation'
  question: string
  options: string[]
  required: boolean
}

export type PendingQuestion = { callId: string; questions: Question[] }

export type Source = { id: string; title: string; url?: string; excerpt?: string; category?: string; corpus?: string }

export type Session = {
  id: number
  title: string
  status: string
  provider_connection_id: number
  model: string | null
  active_skills: string
  pending_question: string | null
  created_at: string
  updated_at: string
  archived_at?: string | null
  case_id?: string | null
  messages?: Message[]
  tool_calls?: Array<{
    call_id: string
    tool_name: string
    status: ToolActivity['status']
    error: string | null
    sources?: string
  }>
}

export type AgentEvent = { event: string; data: Record<string, unknown> }

export type Skill = { name: string; description: string; version: number; tools: string[] }
