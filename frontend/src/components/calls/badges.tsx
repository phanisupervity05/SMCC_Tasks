'use client'

import { Icons } from '@/components/ui/icons'
import { cn } from '@/lib/utils'
import type { CallStatus, CallSummary } from '@/lib/calls-api'

const STATUS: Record<CallStatus, { label: string; className: string }> = {
  received: { label: 'Received', className: 'bg-slate-100 text-slate-700 ring-slate-200' },
  sent_to_auto: { label: 'Sent to Auto', className: 'bg-blue-50 text-blue-700 ring-blue-200' },
  done: { label: 'Done', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700 ring-red-200' },
}

export function StatusBadge({ status }: { status: CallStatus }) {
  const s = STATUS[status] ?? STATUS.received
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset',
        s.className
      )}
    >
      {s.label}
    </span>
  )
}

export function StuckBadge({ minutes }: { minutes: number }) {
  return (
    <span
      className='inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-inset ring-amber-300'
      title={`In "Sent to Auto" for more than ${minutes} minutes`}
    >
      <Icons.alertTriangle className='h-3 w-3' />
      Stuck over {minutes} min
    </span>
  )
}

/** A call a policy marked for review. The reasons are in the tooltip. */
export function FlagBadge({ flags }: { flags: CallSummary['flags'] }) {
  if (!flags?.length) return null
  return (
    <span
      className='inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-inset ring-amber-300'
      title={flags.map((f) => f.message).join(' | ')}
    >
      <Icons.flag className='h-3 w-3' />
      {flags.length === 1 ? 'Needs review' : `Needs review (${flags.length})`}
    </span>
  )
}

/** Which results have arrived. Shown while a call is in progress. */
export function ResultChips({ call }: { call: CallSummary }) {
  const chip = (label: string, arrived: boolean) => (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium',
        arrived ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
      )}
    >
      {arrived ? <Icons.check className='h-3 w-3' /> : <Icons.clock className='h-3 w-3' />}
      {label}
    </span>
  )
  return (
    <div className='flex flex-wrap gap-1'>
      {chip('Lead score', call.results_received.lead_score)}
      {chip('Call audit', call.results_received.call_audit)}
    </div>
  )
}

export function BandPill({ band }: { band: number | null }) {
  if (band === null) return <span className='text-muted-foreground'>-</span>
  const tone =
    band >= 4
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : band >= 2
        ? 'bg-amber-50 text-amber-700 ring-amber-200'
        : 'bg-slate-100 text-slate-700 ring-slate-200'
  return (
    <span className={cn('inline-flex h-7 min-w-7 items-center justify-center rounded-lg px-2 text-sm font-bold ring-1 ring-inset', tone)}>
      {band}
    </span>
  )
}

export function formatDate(iso: string | null, withTime = false): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return withTime ? d.toLocaleString() : d.toLocaleDateString()
}
