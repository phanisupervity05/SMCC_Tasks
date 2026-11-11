import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'

const api = vi.hoisted(() => ({
  policies: [] as unknown[],
  toggled: [] as [number, boolean][],
  removed: [] as number[],
  listError: null as string | null,
  toggleError: null as string | null,
}))

vi.mock('@/lib/api-client', () => ({ ApiError: class extends Error {}, apiClient: {} }))
vi.mock('@/lib/policies-api', () => ({
  policiesApi: {
    list: async () => {
      if (api.listError) throw new Error(api.listError)
      return { items: api.policies }
    },
    catalog: async () => ({ stages: [], actions: [], match_modes: [], fields: [], templates: [] }),
    setEnabled: async (id: number, enabled: boolean) => {
      api.toggled.push([id, enabled])
      if (api.toggleError) throw new Error(api.toggleError)
      api.policies = (api.policies as { id: number }[]).map((p) => (p.id === id ? { ...p, enabled } : p))
      return {}
    },
    remove: async (id: number) => {
      api.removed.push(id)
      api.policies = (api.policies as { id: number }[]).filter((p) => p.id !== id)
      return null
    },
  },
}))
// The builder has its own tests; here it only needs to show that it opened.
vi.mock('./PolicyBuilderDialog', () => ({
  PolicyBuilderDialog: ({ open, initial }: { open: boolean; initial: { name: string } | null }) =>
    open ? <div role='dialog'>{initial ? `Editing ${initial.name}` : 'New policy form'}</div> : null,
}))

import { CommandPolicies } from './CommandPolicies'

const policy = (over: Record<string, unknown> = {}) => ({
  id: 1, name: 'Duplicate Lead ID', description: 'Same lead used twice', enabled: true, stage: 'intake', action: 'flag',
  match_mode: 'all', conditions: [], message: null, summary: ['Earlier calls with the same Lead ID is at least 1'],
  effective_message: 'Duplicate Lead ID: Earlier calls with the same Lead ID is at least 1', source: 'builder',
  natural_language: null, hit_count: 3, created_by: 'a', updated_by: 'phani', created_at: null, updated_at: null, ...over,
})

describe('CommandPolicies', () => {
  beforeEach(() => {
    api.policies = []
    api.toggled = []
    api.removed = []
    api.listError = null
    api.toggleError = null
  })

  it('invites the first policy when there are none', async () => {
    render(<CommandPolicies />)
    expect(await screen.findByText('No policies yet')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: /new policy/i })[0])
    expect(screen.getByRole('dialog')).toHaveTextContent('New policy form')
  })

  it('shows what each policy does, in plain words', async () => {
    api.policies = [
      policy(),
      policy({ id: 2, name: 'Lead ID format', action: 'reject', source: 'ai', hit_count: 1, match_mode: 'any', summary: ['Lead ID does not match format LEAD-####'] }),
      policy({ id: 3, name: 'Hot lead', stage: 'results', hit_count: 0, summary: ['Lead band (0 to 5) is at least 4'] }),
    ]
    render(<CommandPolicies />)
    const dup = (await screen.findByText('Duplicate Lead ID')).closest('.space-y-3')!
    expect(within(dup as HTMLElement).getByText('At intake')).toBeInTheDocument()
    expect(within(dup as HTMLElement).getByText('Flags for review')).toBeInTheDocument()
    expect(within(dup as HTMLElement).getByText('Matched 3 times')).toBeInTheDocument()
    expect(within(dup as HTMLElement).getByText(/when all of these is true/i)).toBeInTheDocument()
    const fmt = screen.getByText('Lead ID format').closest('.space-y-3')! as HTMLElement
    expect(within(fmt).getByText('Rejects')).toBeInTheDocument()
    expect(within(fmt).getByText('Drafted with AI')).toBeInTheDocument()
    expect(within(fmt).getByText('Matched 1 time')).toBeInTheDocument()
    expect(within(fmt).getByText(/when any of these is true/i)).toBeInTheDocument()
    const hot = screen.getByText('Hot lead').closest('.space-y-3')! as HTMLElement
    expect(within(hot).getByText('After results')).toBeInTheDocument()
  })

  it('switches a policy off and back on', async () => {
    api.policies = [policy()]
    render(<CommandPolicies />)
    fireEvent.click(await screen.findByRole('switch', { name: /disable duplicate lead id/i }))
    await waitFor(() => expect(api.toggled).toEqual([[1, false]]))
    fireEvent.click(await screen.findByRole('switch', { name: /enable duplicate lead id/i }))
    await waitFor(() => expect(api.toggled).toEqual([[1, false], [1, true]]))
  })

  it('tells the user when a change could not be made', async () => {
    api.policies = [policy()]
    api.toggleError = 'Policy not found'
    render(<CommandPolicies />)
    fireEvent.click(await screen.findByRole('switch'))
    expect(await screen.findByText('Policy not found')).toBeInTheDocument()
  })

  it('asks before deleting, and keeps the policy if the user backs out', async () => {
    api.policies = [policy()]
    render(<CommandPolicies />)
    fireEvent.click(await screen.findByRole('button', { name: /delete duplicate lead id/i }))
    expect(await screen.findByText('Delete this policy?')).toBeInTheDocument()
    expect(screen.getByText(/calls it already flagged keep their flags/i)).toBeInTheDocument()
    expect(api.removed).toEqual([])
    fireEvent.click(screen.getByRole('button', { name: /keep it/i }))
    await waitFor(() => expect(screen.queryByText('Delete this policy?')).not.toBeInTheDocument())
    expect(api.removed).toEqual([])
    expect(screen.getByText('Duplicate Lead ID')).toBeInTheDocument()
  })

  it('deletes once confirmed', async () => {
    api.policies = [policy()]
    render(<CommandPolicies />)
    fireEvent.click(await screen.findByRole('button', { name: /delete duplicate lead id/i }))
    fireEvent.click(await screen.findByRole('button', { name: /delete policy/i }))
    await waitFor(() => expect(api.removed).toEqual([1]))
    expect(await screen.findByText('No policies yet')).toBeInTheDocument()
  })

  it('opens the builder filled in when editing', async () => {
    api.policies = [policy()]
    render(<CommandPolicies />)
    fireEvent.click(await screen.findByRole('button', { name: /edit duplicate lead id/i }))
    expect(screen.getByRole('dialog')).toHaveTextContent('Editing Duplicate Lead ID')
  })

  it('shows an error instead of an empty list when loading fails', async () => {
    api.listError = 'Could not load the policies.'
    render(<CommandPolicies />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the policies.')
    expect(screen.queryByText('No policies yet')).not.toBeInTheDocument()
  })
})
