'use client'

// Rejected requests: payloads the backend refused (a safe copy, no tokens).
import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/components/ui/icons'
import { callsApi, type RejectedRequest } from '@/lib/calls-api'
import { formatDate } from '@/components/calls/badges'

export default function RejectedRequestsPage() {
  const [rows, setRows] = useState<RejectedRequest[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setRows((await callsApi.rejected()).items)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load rejected requests.')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className='space-y-6'>
      <div className='flex flex-wrap items-end justify-between gap-4'>
        <div>
          <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>Rejected requests</h1>
          <p className='mt-1 text-brand-muted'>
            Calls and results the backend refused. Nothing here was saved as a call.
          </p>
        </div>
        <Button variant='outline' onClick={load}>
          <Icons.refresh className='mr-2 h-4 w-4' />
          Refresh
        </Button>
      </div>

      {error && (
        <div role='alert' className='rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700'>
          {error}
        </div>
      )}

      <Card>
        <div className='overflow-x-auto'>
          <table className='w-full text-left text-sm'>
            <thead className='border-b border-black/[0.06] text-xs uppercase tracking-wider text-brand-muted'>
              <tr>
                <th className='px-4 py-3 font-semibold'>Time</th>
                <th className='px-4 py-3 font-semibold'>Endpoint</th>
                <th className='px-4 py-3 font-semibold'>Reason</th>
                <th className='px-4 py-3 font-semibold'>Payload (safe copy)</th>
              </tr>
            </thead>
            <tbody>
              {rows === null && !error && (
                <tr>
                  <td colSpan={4} className='px-4 py-3'>
                    <Skeleton className='h-6 w-full' />
                  </td>
                </tr>
              )}
              {rows?.length === 0 && (
                <tr>
                  <td colSpan={4} className='px-4 py-12 text-center text-brand-muted'>
                    No rejected requests.
                  </td>
                </tr>
              )}
              {rows?.map((r) => (
                <tr key={r.id} className='border-b border-black/[0.04] align-top'>
                  <td className='whitespace-nowrap px-4 py-3'>{formatDate(r.created_at, true)}</td>
                  <td className='px-4 py-3 font-mono text-xs'>{r.endpoint}</td>
                  <td className='px-4 py-3 text-red-700'>{r.reason}</td>
                  <td className='px-4 py-3'>
                    <details>
                      <summary className='cursor-pointer text-xs font-medium text-brand-navy'>Show</summary>
                      <pre className='mt-2 max-h-60 max-w-md overflow-auto rounded-lg bg-slate-50 p-3 text-xs'>
                        {JSON.stringify(r.payload, null, 2)}
                      </pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
