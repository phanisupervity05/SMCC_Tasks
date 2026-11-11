'use client'

// Call detail: metadata, status, lead score, audit checks, recording link.
import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/components/ui/icons'
import { callsApi, inProgress, type CallDetail } from '@/lib/calls-api'
import { RetryButton } from '@/components/calls/RetryButton'
import { LeadIdForm } from '@/components/calls/LeadIdForm'
import {
  BandPill,
  ResultChips,
  StatusBadge,
  StuckBadge,
  formatDate,
} from '@/components/calls/badges'

const POLL_MS = 4000

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className='text-xs font-medium uppercase tracking-wider text-brand-muted'>{label}</dt>
      <dd className='mt-0.5 text-sm text-brand-navy'>{children ?? '-'}</dd>
    </div>
  )
}

function Quote({ text }: { text: string }) {
  return (
    <blockquote className='border-l-2 border-brand-cornflower pl-3 text-sm italic text-brand-navy/80'>
      &ldquo;{text}&rdquo;
    </blockquote>
  )
}

export default function CallDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const [call, setCall] = useState<CallDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setCall(await callsApi.get(taskId))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load this call.')
    }
  }, [taskId])

  useEffect(() => {
    load()
  }, [load])

  // Poll only while the call is in progress, so arriving results appear on their own.
  const live = call ? inProgress(call.status) : false
  useEffect(() => {
    if (!live) return
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [live, load])

  const back = (
    <Link href='/' className='mb-3 inline-flex items-center text-sm text-brand-muted hover:text-brand-navy'>
      <Icons.arrowLeft className='mr-1 h-4 w-4' /> Calls
    </Link>
  )

  if (error && !call) {
    return (
      <div className='space-y-4'>
        {back}
        <div role='alert' className='rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700'>
          {error}
        </div>
      </div>
    )
  }
  if (!call) {
    return (
      <div className='space-y-4'>
        {back}
        <Skeleton className='h-10 w-80' />
        <Skeleton className='h-48 w-full' />
      </div>
    )
  }

  return (
    <div className='space-y-6'>
      <div>
        {back}
        <div className='flex flex-wrap items-center gap-3'>
          <h1 className='font-mono text-xl font-bold tracking-tight text-brand-navy sm:text-2xl'>
            {call.task_id}
          </h1>
          <StatusBadge status={call.status} />
          {call.is_stuck && <StuckBadge minutes={call.stuck_after_minutes} />}
        </div>
      </div>

      {call.is_stuck && (
        <div role='alert' className='flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900'>
          <Icons.alertTriangle className='mt-0.5 h-5 w-5 shrink-0' />
          <p>
            This call has been in Sent to Auto for more than {call.stuck_after_minutes} minutes
            without a full result.
          </p>
        </div>
      )}

      {call.flags.length > 0 && (
        <div role='status' className='flex items-start gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900'>
          <Icons.flag className='mt-0.5 h-5 w-5 shrink-0' />
          <div>
            <p className='font-semibold'>
              Flagged for review by {call.flags.length} {call.flags.length === 1 ? 'policy' : 'policies'}
            </p>
            <ul className='mt-1 list-disc pl-5'>
              {call.flags.map((f) => (
                <li key={f.policy_id}>
                  <span className='font-medium'>{f.policy}:</span> {f.message}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {call.status === 'failed' && (
        <div role='alert' className='flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800'>
          <Icons.alertCircle className='mt-0.5 h-5 w-5 shrink-0' />
          <div>
            <p className='font-semibold'>This call failed</p>
            <p>{call.failure_reason ?? 'No reason was recorded.'}</p>
            <div className='mt-3'>
              <RetryButton taskId={call.task_id} onDone={load} size='default' />
            </div>
          </div>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Call</CardTitle>
        </CardHeader>
        <CardContent className='space-y-5'>
          <dl className='grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3'>
            <Meta label='Sales agent'>
              {call.agent_name} <span className='text-brand-muted'>({call.agent_id})</span>
            </Meta>
            <Meta label='Customer'>{call.customer_name}</Meta>
            <Meta label='Lead ID'>
              {call.lead_id ?? <LeadIdForm taskId={call.task_id} onDone={load} />}
            </Meta>
            <Meta label='Call date'>{formatDate(call.call_date)}</Meta>
            <Meta label='Received'>{formatDate(call.created_at, true)}</Meta>
            <Meta label='Sent to Auto'>{formatDate(call.sent_to_auto_at, true)}</Meta>
            <Meta label='Last update'>{formatDate(call.updated_at, true)}</Meta>
            {inProgress(call.status) && (
              <Meta label='Results arrived'>
                <ResultChips call={call} />
              </Meta>
            )}
          </dl>
          <a
            href={call.recording_url}
            target='_blank'
            rel='noopener noreferrer'
            className='inline-flex items-center gap-2 break-all rounded-lg border border-border px-3 py-2 text-sm font-medium text-brand-navy hover:bg-secondary'
          >
            <Icons.externalLink className='h-4 w-4 shrink-0' />
            Open recording
          </a>
        </CardContent>
      </Card>

      {call.transcript && (
        <Card>
          <CardHeader>
            <CardTitle>Transcript</CardTitle>
            <CardDescription>Each line is labelled Agent, Customer or Unknown.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className='max-h-96 overflow-auto whitespace-pre-wrap text-sm text-brand-navy'>
              {call.transcript}
            </pre>
          </CardContent>
        </Card>
      )}

      <div className='grid gap-6 lg:grid-cols-2'>
        <Card>
          <CardHeader>
            <CardTitle>Lead score</CardTitle>
            <CardDescription>Band from 0 to 5.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            {call.lead_score ? (
              <>
                <div className='flex items-center gap-3'>
                  <BandPill band={call.lead_score.band} />
                  <span className='text-lg font-semibold text-brand-navy'>
                    {call.lead_score.label ?? `Band ${call.lead_score.band}`}
                  </span>
                </div>
                <div>
                  <p className='text-xs font-medium uppercase tracking-wider text-brand-muted'>Reason</p>
                  <p className='mt-1 text-sm text-brand-navy'>{call.lead_score.reason}</p>
                </div>
                {call.lead_score.evidence.length > 0 && (
                  <div className='space-y-2'>
                    <p className='text-xs font-medium uppercase tracking-wider text-brand-muted'>Evidence</p>
                    {call.lead_score.evidence.map((q, i) => (
                      <Quote key={i} text={q} />
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className='text-sm text-brand-muted'>
                {call.status === 'failed' ? 'No lead score was saved.' : 'Waiting for the lead score.'}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Call audit</CardTitle>
            <CardDescription>Each check is scored from 1 to 5.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            {call.call_audit ? (
              <>
                <p className='text-3xl font-bold text-brand-navy'>
                  {Math.round(call.call_audit.score_percent)}%
                </p>
                {call.call_audit.summary && (
                  <p className='text-sm text-brand-navy'>{call.call_audit.summary}</p>
                )}
                <ul className='divide-y divide-black/[0.05]'>
                  {call.call_audit.checks.map((c, i) => (
                    <li key={i} className='space-y-1.5 py-3 first:pt-0'>
                      <div className='flex items-center justify-between gap-3'>
                        <span className='text-sm font-medium text-brand-navy'>{c.name}</span>
                        <span className='shrink-0 rounded-md bg-brand-cornflower/20 px-2 py-0.5 text-sm font-bold text-brand-navy'>
                          {c.score}/5
                        </span>
                      </div>
                      {c.evidence.map((q, j) => (
                        <Quote key={j} text={q} />
                      ))}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className='text-sm text-brand-muted'>
                {call.status === 'failed' ? 'No call audit was saved.' : 'Waiting for the call audit.'}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {call.auto_output != null && (
        <Card>
          <CardHeader>
            <CardTitle>Auto output (JSON)</CardTitle>
            <CardDescription>The final result as the Auto workflow returned it.</CardDescription>
          </CardHeader>
          <CardContent>
            <details>
              <summary className='cursor-pointer text-sm font-medium text-brand-navy'>Show JSON</summary>
              <pre className='mt-3 max-h-96 overflow-auto rounded-lg bg-secondary p-3 text-xs text-brand-navy'>
                {JSON.stringify(call.auto_output, null, 2)}
              </pre>
            </details>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
