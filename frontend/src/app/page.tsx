'use client'

// Calls list: the home screen. Filters are sent to the backend as query parameters.
import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { Icons } from '@/components/ui/icons'
import { cn } from '@/lib/utils'
import {
  callsApi,
  inProgress,
  type CallFilters,
  type CallSummary,
  type CallsStats,
} from '@/lib/calls-api'
import { RetryButton } from '@/components/calls/RetryButton'
import { CallsDashboard } from '@/components/calls/Dashboard'
import {
  BandPill,
  ResultChips,
  FlagBadge,
  StatusBadge,
  StuckBadge,
  formatDate,
} from '@/components/calls/badges'

const ALL = 'all'
const POLL_MS = 5000
const PAGE_SIZE = 25

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <div className='min-w-[11rem] space-y-1'>
      <p className='text-xs font-medium text-brand-muted'>{label}</p>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All</SelectItem>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

export default function CallsPage() {
  const router = useRouter()
  const [band, setBand] = useState(ALL)
  const [agent, setAgent] = useState(ALL)
  const [status, setStatus] = useState(ALL)
  const [review, setReview] = useState(ALL)
  const [agents, setAgents] = useState<{ agent_id: string; agent_name: string }[]>([])
  const [calls, setCalls] = useState<CallSummary[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [exporting, setExporting] = useState(false)
  const [stats, setStats] = useState<CallsStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const filtersRef = useRef<CallFilters>({})

  const load = useCallback(async () => {
    try {
      const [res, st] = await Promise.all([
        callsApi.list(filtersRef.current),
        callsApi
          .stats({ date_from: filtersRef.current.date_from, date_to: filtersRef.current.date_to })
          .catch(() => null),
      ])
      setCalls(res.items)
      setTotal(res.total)
      if (st) setStats(st)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load calls.')
    }
  }, [])

  // Filters changed: tell the backend, reload.
  useEffect(() => {
    filtersRef.current = {
      band: band === ALL ? undefined : band,
      agent_id: agent === ALL ? undefined : agent,
      status: status === ALL ? undefined : status,
      flagged: review === 'flagged' ? true : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }
    setCalls(null)
    load()
  }, [band, agent, status, review, dateFrom, dateTo, page, load])

  // A new filter starts again from the first page.
  useEffect(() => {
    setPage(0)
  }, [band, agent, status, review, dateFrom, dateTo])

  useEffect(() => {
    callsApi.agents().then(setAgents).catch(() => setAgents([]))
  }, [])

  // Keep results arriving live, but not while the tab is hidden.
  useEffect(() => {
    const tick = () => {
      if (!document.hidden) load()
    }
    const t = setInterval(tick, POLL_MS)
    document.addEventListener('visibilitychange', tick)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', tick)
    }
  }, [load])

  const rangeInvalid = !!dateFrom && !!dateTo && dateFrom > dateTo

  const exportCsv = async () => {
    setExporting(true)
    try {
      const { blob, filename } = await callsApi.exportCsv({ ...filtersRef.current, limit: undefined, offset: undefined })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not export the calls.')
    } finally {
      setExporting(false)
    }
  }

  const stuck = (calls ?? []).filter((c) => c.is_stuck)

  return (
    <div className='space-y-6'>
      <div className='flex flex-wrap items-end justify-between gap-4'>
        <div>
          <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>Calls Dashboard</h1>
          <p className='mt-1 text-brand-muted'>
            Statistics and analytics for lead scores and call audits across every sales call.
          </p>
        </div>
        <div className='flex gap-2'>
          <Button variant='outline' onClick={load}>
            <Icons.refresh className='mr-2 h-4 w-4' />
            Refresh
          </Button>
          <Button variant='outline' onClick={exportCsv} disabled={exporting || rangeInvalid}>
            <Icons.download className='mr-2 h-4 w-4' />
            {exporting ? 'Exporting...' : 'Export CSV'}
          </Button>
          <Button asChild>
            <Link href='/calls/new'>
              <Icons.plus className='mr-2 h-4 w-4' />
              Drop a call
            </Link>
          </Button>
        </div>
      </div>

      {stuck.length > 0 && (
        <div
          role='alert'
          className='flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900'
        >
          <Icons.alertTriangle className='mt-0.5 h-5 w-5 shrink-0' />
          <div>
            <p className='font-semibold'>
              {stuck.length} {stuck.length === 1 ? 'call is' : 'calls are'} stuck in Sent to Auto
            </p>
            <p>
              No full result after more than {stuck[0].stuck_after_minutes} minutes. Check the
              Orchestrator.
            </p>
          </div>
        </div>
      )}

      <CallsDashboard stats={stats} />

      <h2 className='pt-2 text-lg font-semibold text-brand-navy'>All calls</h2>

      <Card>
        <CardContent className='flex flex-wrap gap-4 pt-6'>
          <FilterSelect
            label='Band'
            value={band}
            onChange={setBand}
            options={[0, 1, 2, 3, 4, 5].map((b) => ({ value: String(b), label: `Band ${b}` }))}
          />
          <FilterSelect
            label='Sales agent'
            value={agent}
            onChange={setAgent}
            options={agents.map((a) => ({ value: a.agent_id, label: `${a.agent_name} (${a.agent_id})` }))}
          />
          <div className='space-y-1'>
            <p className='text-xs font-medium text-brand-muted'>From</p>
            <Input type='date' aria-label='From date' value={dateFrom} max={dateTo || undefined} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className='space-y-1'>
            <p className='text-xs font-medium text-brand-muted'>To</p>
            <Input type='date' aria-label='To date' value={dateTo} min={dateFrom || undefined} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          {(dateFrom || dateTo) && (
            <Button
              variant='ghost'
              className='self-end'
              onClick={() => {
                setDateFrom('')
                setDateTo('')
              }}
            >
              Clear dates
            </Button>
          )}
          <FilterSelect
            label='Review'
            value={review}
            onChange={setReview}
            options={[{ value: 'flagged', label: 'Flagged for review' }]}
          />
          <FilterSelect
            label='Status'
            value={status}
            onChange={setStatus}
            options={[
              { value: 'received', label: 'Received' },
              { value: 'sent_to_auto', label: 'Sent to Auto' },
              { value: 'done', label: 'Done' },
              { value: 'failed', label: 'Failed' },
            ]}
          />
        </CardContent>
      </Card>

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
                <th className='px-4 py-3 font-semibold'>Call</th>
                <th className='px-4 py-3 font-semibold'>Sales agent</th>
                <th className='px-4 py-3 font-semibold'>Customer</th>
                <th className='px-4 py-3 font-semibold'>Call date</th>
                <th className='px-4 py-3 font-semibold'>Band</th>
                <th className='px-4 py-3 font-semibold'>Audit score</th>
                <th className='px-4 py-3 font-semibold'>Status</th>
              </tr>
            </thead>
            <tbody>
              {calls === null &&
                !error &&
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className='border-b border-black/[0.04]'>
                    <td colSpan={7} className='px-4 py-3'>
                      <Skeleton className='h-6 w-full' />
                    </td>
                  </tr>
                ))}
              {calls?.length === 0 && (
                <tr>
                  <td colSpan={7} className='px-4 py-12 text-center text-brand-muted'>
                    No calls match these filters.{' '}
                    <Link href='/calls/new' className='font-medium text-brand-navy underline'>
                      Drop a call
                    </Link>
                  </td>
                </tr>
              )}
              {calls?.map((c) => (
                <tr
                  key={c.task_id}
                  onClick={() => router.push(`/calls/${c.task_id}`)}
                  className={cn(
                    'cursor-pointer border-b border-black/[0.04] transition-colors hover:bg-brand-cornflower/10',
                    c.is_stuck && 'bg-amber-50/70'
                  )}
                >
                  <td className='px-4 py-3'>
                    <Link
                      href={`/calls/${c.task_id}`}
                      onClick={(e) => e.stopPropagation()}
                      className='font-mono text-xs font-medium text-brand-navy hover:underline'
                    >
                      {c.task_id}
                    </Link>
                    {c.lead_id && <p className='text-xs text-brand-muted'>Lead {c.lead_id}</p>}
                  </td>
                  <td className='px-4 py-3'>
                    <p className='font-medium text-brand-navy'>{c.agent_name}</p>
                    <p className='text-xs text-brand-muted'>{c.agent_id}</p>
                  </td>
                  <td className='px-4 py-3'>{c.customer_name ?? <span className='text-muted-foreground'>-</span>}</td>
                  <td className='whitespace-nowrap px-4 py-3'>{formatDate(c.call_date)}</td>
                  <td className='px-4 py-3'>
                    <BandPill band={c.lead_band} />
                  </td>
                  <td className='px-4 py-3 font-medium'>
                    {c.audit_score_percent !== null ? `${Math.round(c.audit_score_percent)}%` : <span className='text-muted-foreground'>-</span>}
                  </td>
                  <td className='px-4 py-3'>
                    <div className='flex flex-col items-start gap-1.5'>
                      <div className='flex flex-wrap items-center gap-1.5'>
                        <StatusBadge status={c.status} />
                        {c.is_stuck && <StuckBadge minutes={c.stuck_after_minutes} />}
                        <FlagBadge flags={c.flags} />
                      </div>
                      {inProgress(c.status) && <ResultChips call={c} />}
                      {c.status === 'failed' && c.failure_reason && (
                        <p className='max-w-xs truncate text-xs text-red-700' title={c.failure_reason}>
                          {c.failure_reason}
                        </p>
                      )}
                      {c.status === 'failed' && <RetryButton taskId={c.task_id} onDone={load} />}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {calls && calls.length > 0 && (
          <div className='flex items-center justify-between border-t border-black/[0.04] px-4 py-3 text-xs text-brand-muted'>
            <span>
              Showing {page * PAGE_SIZE + 1}-{page * PAGE_SIZE + calls.length} of {total}
            </span>
            <div className='flex gap-2'>
              <Button variant='outline' size='sm' disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                Previous
              </Button>
              <Button
                variant='outline'
                size='sm'
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
