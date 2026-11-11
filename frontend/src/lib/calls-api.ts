// frontend/src/lib/calls-api.ts
// Types and calls for the Calls API. Display and send only: every rule lives in the backend.
import apiClientFetch, { apiClient } from '@/lib/api-client'

export type CallStatus = 'received' | 'sent_to_auto' | 'done' | 'failed'

export interface CallSummary {
  task_id: string
  lead_id: string | null
  agent_id: string
  agent_name: string
  customer_name: string | null
  call_date: string | null
  status: CallStatus
  failure_reason: string | null
  is_stuck: boolean
  stuck_after_minutes: number
  results_received: { lead_score: boolean; call_audit: boolean }
  lead_band: number | null
  audit_score_percent: number | null
  sent_to_auto_at: string | null
  created_at: string
  updated_at: string
}

export interface AuditCheck {
  name: string
  score: number
  evidence: string[]
}

export interface CallDetail extends CallSummary {
  recording_url: string
  transcript: string | null
  auto_output: unknown | null
  lead_score: {
    band: number
    label: string | null
    reason: string
    evidence: string[]
    created_at: string
  } | null
  call_audit: {
    checks: AuditCheck[]
    score_percent: number
    summary: string | null
    created_at: string
  } | null
}

export interface CallsConfig {
  stuck_after_minutes: number
  statuses: CallStatus[]
  // AUTO STUB START
  test_mode: boolean
  stub_scenarios: { value: string; label: string }[]
  // AUTO STUB END
}

export interface RejectedRequest {
  id: number
  endpoint: string
  reason: string
  payload: unknown
  created_at: string
}

export interface CallFilters {
  band?: string
  agent_id?: string
  status?: string
}

export interface CallsStats {
  total: number
  processed: number
  in_progress: number
  failed: number
  rejected: number
  stuck: number
  success_rate: number | null
  avg_audit_percent: number | null
  avg_band: number | null
  by_status: Record<CallStatus, number>
  bands: { band: number; count: number }[]
  per_day: { date: string; count: number }[]
  agents: {
    agent_id: string
    agent_name: string
    calls: number
    done: number
    avg_band: number | null
    avg_audit_percent: number | null
  }[]
}

export interface AutoPolicy {
  policy_id: string
  name: string
  agent: string
  description: string
  workspace: string
  version: number
  published: boolean
  updated_at: string
  url: string
  inputs: string[]
  outputs: { field: string; values: string[] }[]
  judgments: { name: string; answers: string[]; rubric: string }[]
  rules_title: string
  rules: string[]
}

export const callsApi = {
  autoPolicies: () => apiClient.get<{ items: AutoPolicy[] }>('/api/calls/auto-policies'),
  stats: () => apiClient.get<CallsStats>('/api/calls/stats'),
  config: () => apiClient.get<CallsConfig>('/api/calls/config'),
  agents: () =>
    apiClient.get<{ agent_id: string; agent_name: string }[]>('/api/calls/agents'),
  list: (f: CallFilters) => {
    const q = new URLSearchParams()
    if (f.band) q.set('band', f.band)
    if (f.agent_id) q.set('agent_id', f.agent_id)
    if (f.status) q.set('status', f.status)
    return apiClient.get<{ total: number; items: CallSummary[] }>(
      `/api/calls?${q.toString()}`
    )
  },
  get: (taskId: string) =>
    apiClient.get<CallDetail>(`/api/calls/${encodeURIComponent(taskId)}`),
  uploadAudio: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    // No Content-Type header: the browser sets the multipart boundary itself.
    return apiClientFetch<{ url: string; filename: string; size: number }>(
      '/api/calls/upload-audio',
      { method: 'POST', body: form }
    )
  },
  retry: (taskId: string) =>
    apiClient.post<CallDetail>(`/api/calls/${encodeURIComponent(taskId)}/retry`, {}),
  drop: (body: Record<string, string>) =>
    apiClient.post<{ created: boolean; call: CallDetail }>('/api/calls', body),
  rejected: () =>
    apiClient.get<{ items: RejectedRequest[] }>('/api/rejected-requests'),
}

export const inProgress = (s: CallStatus) => s === 'received' || s === 'sent_to_auto'
