import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// Plain functions (not vi.fn) stand in for the API, so a rejected call is handled only by the component.
const api = vi.hoisted(() => ({
  created: [] as unknown[],
  updated: [] as unknown[],
  create: (async () => ({})) as (p: unknown) => Promise<unknown>,
  test: (async () => ({ checked: 0, matched: 0, examples: [] })) as (p: unknown) => Promise<unknown>,
  fromText: (async () => ({})) as (t: string) => Promise<unknown>,
}))

vi.mock('@/lib/api-client', () => {
  class ApiError extends Error {
    status: number
    fieldErrors?: { field: string; message: string }[]
    constructor(message: string, status: number, fieldErrors?: { field: string; message: string }[]) {
      super(message)
      this.status = status
      this.fieldErrors = fieldErrors
    }
  }
  return { ApiError, apiClient: {} }
})
vi.mock('@/lib/policies-api', () => ({
  policiesApi: {
    create: (p: unknown) => {
      api.created.push(p)
      return api.create(p)
    },
    update: (id: number, p: unknown) => {
      api.updated.push([id, p])
      return Promise.resolve({})
    },
    test: (p: unknown) => api.test(p),
    fromText: (t: string) => api.fromText(t),
  },
}))

import { ApiError } from '@/lib/api-client'
import type { CommandPolicy, PolicyCatalog } from '@/lib/policies-api'
import { PolicyBuilderDialog } from './PolicyBuilderDialog'

const ops = (kind: 'text' | 'number') =>
  kind === 'text'
    ? [
        { value: 'equals', label: 'equals', needs_value: true },
        { value: 'in_list', label: 'is one of', needs_value: true },
        { value: 'is_empty', label: 'is empty', needs_value: false },
      ]
    : [
        { value: 'gte', label: 'is at least', needs_value: true },
        { value: 'lt', label: 'is less than', needs_value: true },
      ]

const catalog: PolicyCatalog = {
  stages: [
    { value: 'intake', label: 'At intake' },
    { value: 'results', label: 'After results' },
  ],
  actions: [
    { value: 'flag', label: 'Flag for review' },
    { value: 'reject', label: 'Reject the request' },
  ],
  match_modes: [
    { value: 'all', label: 'All conditions' },
    { value: 'any', label: 'Any condition' },
  ],
  fields: [
    { key: 'lead_id', label: 'Lead ID', type: 'text', stages: ['intake', 'results'], group: 'Call details', operators: ops('text') },
    { key: 'lead_id_calls', label: 'Earlier calls with the same Lead ID', type: 'number', stages: ['intake', 'results'], group: 'Compared with the database', help: 'Use at least 1 to catch a duplicate.', operators: ops('number') },
    { key: 'lead_band', label: 'Lead band', type: 'number', stages: ['results'], group: 'Results', operators: ops('number') },
  ],
  templates: [
    {
      id: 'dup', title: 'Duplicate Lead ID', summary: 's',
      policy: { name: 'Duplicate Lead ID', stage: 'intake', action: 'flag', match_mode: 'all', conditions: [{ field: 'lead_id_calls', operator: 'gte', value: 1 }] },
    },
  ],
}

function open(initial: CommandPolicy | null = null, onSaved = () => {}) {
  render(<PolicyBuilderDialog open onOpenChange={() => {}} catalog={catalog} initial={initial} onSaved={onSaved} />)
}

const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } })

describe('PolicyBuilderDialog', () => {
  beforeEach(() => {
    api.created = []
    api.updated = []
    api.create = async () => ({})
    api.test = async () => ({ checked: 0, matched: 0, examples: [] })
    api.fromText = async () => ({})
  })

  it('saves a hand-built policy with exactly what was entered', async () => {
    const onSaved = vi.fn()
    open(null, onSaved)
    type('Name', 'Lead ID format')
    type('When does it run?', 'intake')
    type('What happens on a match?', 'reject')
    type('Condition 1 field', 'lead_id')
    type('Condition 1 operator', 'in_list')
    type('Condition 1 value', 'LEAD-1, LEAD-2')
    type(/Message shown/i, 'Not allowed')
    fireEvent.click(screen.getByRole('button', { name: /create policy/i }))
    await waitFor(() => expect(onSaved).toHaveBeenCalled())
    expect(api.created).toEqual([
      {
        name: 'Lead ID format', description: null, stage: 'intake', action: 'reject', match_mode: 'all',
        message: 'Not allowed', enabled: true, source: 'builder', natural_language: null,
        conditions: [{ field: 'lead_id', operator: 'in_list', value: 'LEAD-1, LEAD-2' }],
      },
    ])
  })

  it('hides the value box for "is empty" and sends no value', async () => {
    open()
    type('Name', 'Needs a Lead ID')
    type('Condition 1 field', 'lead_id')
    type('Condition 1 operator', 'is_empty')
    expect(screen.queryByLabelText('Condition 1 value')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /create policy/i }))
    await waitFor(() => expect(api.created.length).toBe(1))
    expect((api.created[0] as { conditions: unknown[] }).conditions).toEqual([{ field: 'lead_id', operator: 'is_empty', value: null }])
  })

  it('after results a policy can only flag, and results-only fields are offered', () => {
    open()
    expect(screen.queryByRole('option', { name: 'Lead band' })).not.toBeInTheDocument() // not known at intake
    type('What happens on a match?', 'reject')
    type('When does it run?', 'results')
    expect((screen.getByLabelText('What happens on a match?') as HTMLSelectElement).value).toBe('flag')
    expect(screen.getByRole('option', { name: 'Reject the request' })).toBeDisabled()
    expect(screen.getByRole('option', { name: 'Lead band' })).toBeInTheDocument()
  })

  it('moving back to intake replaces a condition on a results-only field', () => {
    open()
    type('When does it run?', 'results')
    type('Condition 1 field', 'lead_band')
    type('When does it run?', 'intake')
    expect((screen.getByLabelText('Condition 1 field') as HTMLSelectElement).value).not.toBe('lead_band')
  })

  it('adds and removes conditions, keeping at least one', () => {
    open()
    expect(screen.getByRole('button', { name: /remove condition 1/i })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /add condition/i }))
    expect(screen.getByLabelText('Condition 2 field')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /remove condition 2/i }))
    expect(screen.queryByLabelText('Condition 2 field')).not.toBeInTheDocument()
  })

  it('shows the backend errors next to the field at fault and does not close', async () => {
    api.create = async () => {
      throw new ApiError('x', 422, [
        { field: 'name', message: 'must be at least 3 characters' },
        { field: 'conditions[0].value', message: 'needs a value' },
        { field: 'policy', message: 'something else' },
      ])
    }
    const onSaved = vi.fn()
    open(null, onSaved)
    fireEvent.click(screen.getByRole('button', { name: /create policy/i }))
    expect(await screen.findByText('must be at least 3 characters')).toBeInTheDocument()
    expect(screen.getByText('needs a value')).toBeInTheDocument()
    expect(screen.getByText('something else')).toBeInTheDocument()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('starts from a template', () => {
    open()
    type('Start from a template', 'dup')
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Duplicate Lead ID')
    expect((screen.getByLabelText('Condition 1 field') as HTMLSelectElement).value).toBe('lead_id_calls')
    expect((screen.getByLabelText('Condition 1 value') as HTMLInputElement).value).toBe('1')
  })

  it('fills the form from an AI draft, keeps it off, and asks for review', async () => {
    api.fromText = async () => ({
      draft: {
        name: 'Hot lead', stage: 'results', action: 'flag', match_mode: 'all', enabled: false, source: 'ai',
        natural_language: 'flag hot leads', conditions: [{ field: 'lead_band', operator: 'gte', value: 4 }],
      },
    })
    open()
    type('Describe the policy', 'Flag hot leads after scoring')
    fireEvent.click(screen.getByRole('button', { name: /draft with ai/i }))
    expect(await screen.findByText(/check every part below/i)).toBeInTheDocument()
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Hot lead')
    expect((screen.getByLabelText('When does it run?') as HTMLSelectElement).value).toBe('results')
    expect((screen.getByRole('switch') as HTMLButtonElement).getAttribute('aria-checked')).toBe('false')
    expect(api.created).toEqual([]) // drafting saves nothing
    fireEvent.click(screen.getByRole('button', { name: /create policy/i }))
    await waitFor(() => expect(api.created.length).toBe(1))
    expect(api.created[0]).toMatchObject({ source: 'ai', natural_language: 'flag hot leads', enabled: false })
  })

  it('shows why a draft failed and leaves the form alone', async () => {
    api.fromText = async () => {
      throw new Error('AI drafting is not available right now. Use the rule builder instead.')
    }
    open()
    type('Name', 'Keep me')
    type('Describe the policy', 'Flag hot leads after scoring')
    fireEvent.click(screen.getByRole('button', { name: /draft with ai/i }))
    expect(await screen.findByText(/not available right now/i)).toBeInTheDocument()
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Keep me')
  })

  it('needs a real sentence before drafting', () => {
    open()
    expect(screen.getByRole('button', { name: /draft with ai/i })).toBeDisabled()
    type('Describe the policy', 'short')
    expect(screen.getByRole('button', { name: /draft with ai/i })).toBeDisabled()
  })

  it('tests a policy on recent calls and says nothing was changed', async () => {
    api.test = async () => ({ checked: 50, matched: 3, examples: [{ task_id: 'call_x', agent_name: 'Asha', lead_id: 'L-1' }] })
    open()
    fireEvent.click(screen.getByRole('button', { name: /test on recent calls/i }))
    expect(await screen.findByText(/would match 3 of the last 50 calls/i)).toBeInTheDocument()
    expect(screen.getByText(/call_x \(Asha, Lead L-1\)/)).toBeInTheDocument()
    expect(screen.getByText(/nothing was flagged or saved/i)).toBeInTheDocument()
  })

  it('edits an existing policy with its values filled in', async () => {
    const existing = {
      id: 7, name: 'Old name', description: 'd', stage: 'intake', action: 'flag', match_mode: 'any', message: 'm', enabled: true,
      conditions: [{ field: 'lead_id', operator: 'equals', value: 'X' }], source: 'builder', natural_language: null,
      summary: [], effective_message: 'm', hit_count: 2, created_by: null, updated_by: null, created_at: null, updated_at: null,
    } as CommandPolicy
    open(existing)
    expect(screen.queryByLabelText('Describe the policy')).not.toBeInTheDocument() // no AI box when editing
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Old name')
    type('Name', 'New name')
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }))
    await waitFor(() => expect(api.updated.length).toBe(1))
    expect((api.updated[0] as [number, { name: string; match_mode: string }])[0]).toBe(7)
    expect((api.updated[0] as [number, { name: string; match_mode: string }])[1]).toMatchObject({ name: 'New name', match_mode: 'any' })
  })
})
