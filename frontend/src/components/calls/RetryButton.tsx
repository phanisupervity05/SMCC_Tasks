'use client'

// Re-run a failed call. The backend decides whether it is allowed; this only sends the request.
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { callsApi } from '@/lib/calls-api'

export function RetryButton({
  taskId,
  onDone,
  size = 'sm',
}: {
  taskId: string
  onDone: () => void
  size?: 'sm' | 'default'
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async (e: React.MouseEvent) => {
    e.stopPropagation() // do not open the row
    setBusy(true)
    setError(null)
    try {
      await callsApi.retry(taskId)
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not re-run this call.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className='flex flex-col items-start gap-1'>
      <Button variant='outline' size={size} onClick={run} disabled={busy}>
        <Icons.refresh className={`mr-1.5 h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} />
        {busy ? 'Re-running...' : 'Re-run'}
      </Button>
      {error && <p className='max-w-xs text-xs text-red-700'>{error}</p>}
    </div>
  )
}
