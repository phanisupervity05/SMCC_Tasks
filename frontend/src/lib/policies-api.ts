// frontend/src/lib/policies-api.ts
// Types and calls for the Command Center policies API. Display and send only: every rule is checked by the backend.
import { apiClient } from '@/lib/api-client'

export type Stage = 'intake' | 'results'
export type PolicyAction = 'flag' | 'reject'
export type MatchMode = 'all' | 'any'

export interface Condition {
  field: string
  operator: string
  value: string | number | null
}

export interface PolicyInput {
  name: string
  description?: string | null
  stage: Stage
  action: PolicyAction
  match_mode: MatchMode
  message?: string | null
  conditions: Condition[]
  enabled?: boolean
  source?: 'builder' | 'ai'
  natural_language?: string | null
}

export interface CommandPolicy extends PolicyInput {
  id: number
  enabled: boolean
  summary: string[]
  effective_message: string
  source: 'builder' | 'ai'
  hit_count: number
  created_by: string | null
  updated_by: string | null
  created_at: string | null
  updated_at: string | null
}

export interface CatalogOperator {
  value: string
  label: string
  needs_value: boolean
}

export interface CatalogField {
  key: string
  label: string
  type: 'text' | 'number'
  stages: Stage[]
  group: string
  help?: string
  operators: CatalogOperator[]
}

export interface PolicyTemplate {
  id: string
  title: string
  summary: string
  policy: PolicyInput
}

export interface PolicyCatalog {
  stages: { value: Stage; label: string }[]
  actions: { value: PolicyAction; label: string }[]
  match_modes: { value: MatchMode; label: string }[]
  fields: CatalogField[]
  templates: PolicyTemplate[]
}

export interface PolicyTestResult {
  checked: number
  matched: number
  examples: { task_id: string; agent_name: string; lead_id: string | null }[]
}

export const policiesApi = {
  catalog: () => apiClient.get<PolicyCatalog>('/api/policies/catalog'),
  list: () => apiClient.get<{ items: CommandPolicy[] }>('/api/policies'),
  create: (p: PolicyInput) => apiClient.post<CommandPolicy>('/api/policies', p),
  update: (id: number, p: PolicyInput) => apiClient.put<CommandPolicy>(`/api/policies/${id}`, p),
  setEnabled: (id: number, enabled: boolean) =>
    apiClient.patch<CommandPolicy>(`/api/policies/${id}/enabled`, { enabled }),
  remove: (id: number) => apiClient.delete<null>(`/api/policies/${id}`),
  test: (p: PolicyInput) => apiClient.post<PolicyTestResult>('/api/policies/test', p),
  fromText: (text: string) =>
    apiClient.post<{ draft: PolicyInput }>('/api/policies/from-text', { text }),
}
