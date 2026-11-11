import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// A plain function (not vi.fn) stands in for the API, so a rejected call is handled only by the component.
const api = vi.hoisted(() => ({
  calls: [] as [string, string][],
  impl: (async () => ({})) as (taskId: string, leadId: string) => Promise<unknown>,
}))
vi.mock('@/lib/calls-api', () => ({
  callsApi: {
    setLeadId: (taskId: string, leadId: string) => {
      api.calls.push([taskId, leadId])
      return api.impl(taskId, leadId)
    },
  },
}))

import { LeadIdForm } from './LeadIdForm'

describe('LeadIdForm', () => {
  beforeEach(() => {
    api.calls = []
    api.impl = async () => ({})
  })

  it('cannot be saved while empty', () => {
    render(<LeadIdForm taskId='call_1' onDone={() => {}} />)
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Lead ID'), { target: { value: '   ' } })
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })

  it('saves the typed Lead ID and reloads', async () => {
    const onDone = vi.fn()
    render(<LeadIdForm taskId='call_1' onDone={onDone} />)
    fireEvent.change(screen.getByLabelText('Lead ID'), { target: { value: 'L-42' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(api.calls).toEqual([['call_1', 'L-42']])
  })

  it('shows the backend message when the call already has a Lead ID', async () => {
    api.impl = async () => {
      throw new Error('This call already has a Lead ID.')
    }
    const onDone = vi.fn()
    render(<LeadIdForm taskId='call_1' onDone={onDone} />)
    fireEvent.change(screen.getByLabelText('Lead ID'), { target: { value: 'L-42' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(screen.getByText(/already has a lead id/i)).toBeInTheDocument())
    expect(onDone).not.toHaveBeenCalled()
  })
})
