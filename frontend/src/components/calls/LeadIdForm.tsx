'use client'

// For a call saved before Lead ID was required. The backend refuses to overwrite an existing one.
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { callsApi } from '@/lib/calls-api'

export function LeadIdForm({ taskId, onDone }: { taskId: string; onDone: () => void }) {
  const [value, setValue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await callsApi.setLeadId(taskId, value)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the Lead ID.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} className='space-y-1'>
      <div className='flex items-center gap-2'>
        <Input
          aria-label='Lead ID'
          placeholder='Enter Lead ID'
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className='h-8 w-44'
        />
        <Button type='submit' size='sm' disabled={busy || !value.trim()}>
          {busy ? 'Saving...' : 'Save'}
        </Button>
      </div>
      {error && <p className='text-xs text-red-700'>{error}</p>}
    </form>
  )
}
