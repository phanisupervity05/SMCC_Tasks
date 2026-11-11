import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// A plain function (not vi.fn) stands in for the API, so a rejected call is handled only by the component.
const api = vi.hoisted(() => ({
  calls: [] as string[],
  impl: (async () => ({})) as (taskId: string) => Promise<unknown>,
}))
vi.mock('@/lib/calls-api', () => ({
  callsApi: {
    retry: (taskId: string) => {
      api.calls.push(taskId)
      return api.impl(taskId)
    },
  },
}))

import { RetryButton } from './RetryButton'

describe('RetryButton', () => {
  beforeEach(() => {
    api.calls = []
    api.impl = async () => ({})
  })

  it('re-runs the call and tells the screen to reload', async () => {
    const onDone = vi.fn()
    render(<RetryButton taskId='call_1' onDone={onDone} />)
    fireEvent.click(screen.getByRole('button', { name: /re-run/i }))
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1))
    expect(api.calls).toEqual(['call_1'])
  })

  it('does not trigger the row click', async () => {
    const rowClick = vi.fn()
    render(
      <div onClick={rowClick}>
        <RetryButton taskId='call_1' onDone={() => {}} />
      </div>
    )
    fireEvent.click(screen.getByRole('button', { name: /re-run/i }))
    await waitFor(() => expect(api.calls.length).toBe(1))
    expect(rowClick).not.toHaveBeenCalled()
  })

  it('shows the error and does not reload when the backend refuses', async () => {
    api.impl = async () => {
      throw new Error('Only a failed call can be run again.')
    }
    const onDone = vi.fn()
    render(<RetryButton taskId='call_1' onDone={onDone} />)
    fireEvent.click(screen.getByRole('button', { name: /re-run/i }))
    await waitFor(() => expect(screen.getByText(/only a failed call/i)).toBeInTheDocument())
    expect(onDone).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /re-run/i })).toBeEnabled()
  })

  it('is disabled while a run is starting, so a double click cannot start two', async () => {
    let finish: (v: unknown) => void = () => {}
    api.impl = () => new Promise((r) => (finish = r))
    render(<RetryButton taskId='call_1' onDone={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /re-run/i }))
    const busy = await screen.findByRole('button', { name: /re-running/i })
    expect(busy).toBeDisabled()
    fireEvent.click(busy)
    expect(api.calls.length).toBe(1)
    finish({})
  })
})
