'use client'

// The two Supervity Auto policies the call agent uses, read only.
import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Icons } from '@/components/ui/icons'
import { callsApi, type AutoPolicy, type AutoPolicySnapshot } from '@/lib/calls-api'
import { formatDate } from '@/components/calls/badges'

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className='rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-700'>{children}</span>
  )
}

function PolicyPanel({ policy }: { policy: AutoPolicy }) {
  return (
    <Card>
      <CardHeader>
        <div className='flex flex-wrap items-start justify-between gap-3'>
          <div>
            <p className='text-xs font-semibold uppercase tracking-wider text-brand-muted'>{policy.agent}</p>
            <CardTitle className='mt-1'>{policy.name}</CardTitle>
          </div>
          <div className='flex flex-wrap items-center gap-2'>
            <span className='inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200'>
              {policy.published ? 'Published' : 'Draft'} v{policy.version}
            </span>
            <a
              href={policy.url}
              target='_blank'
              rel='noreferrer'
              className='inline-flex items-center gap-1 text-xs font-medium text-brand-navy underline'
            >
              Open in Auto
              <Icons.externalLink className='h-3 w-3' />
            </a>
          </div>
        </div>
        <CardDescription className='pt-2'>{policy.description}</CardDescription>
        <p className='pt-1 text-xs text-brand-muted'>
          Workspace {policy.workspace} · Updated {formatDate(policy.updated_at)}
        </p>
      </CardHeader>

      <CardContent className='space-y-6'>
        <div className='grid gap-4 sm:grid-cols-2'>
          <div>
            <h3 className='mb-2 text-sm font-semibold text-brand-navy'>Input</h3>
            <div className='flex flex-wrap gap-1.5'>
              {policy.inputs.map((i) => (
                <Chip key={i}>{i}</Chip>
              ))}
            </div>
          </div>
          <div>
            <h3 className='mb-2 text-sm font-semibold text-brand-navy'>Output</h3>
            <ul className='space-y-1.5 text-sm'>
              {policy.outputs.map((o) => (
                <li key={o.field} className='flex flex-wrap items-center gap-1.5'>
                  <Chip>{o.field}</Chip>
                  <span className='text-xs text-brand-muted'>{o.values.join(', ')}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div>
          <h3 className='mb-2 text-sm font-semibold text-brand-navy'>{policy.rules_title}</h3>
          <ol className='list-decimal space-y-1 pl-5 text-sm text-brand-navy/90'>
            {policy.rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ol>
        </div>

        <div>
          <h3 className='mb-2 text-sm font-semibold text-brand-navy'>
            AI Judgments ({policy.judgments.length})
          </h3>
          <div className='space-y-2'>
            {policy.judgments.map((j) => (
              <details key={j.name} className='group rounded-lg border border-black/[0.06] px-3 py-2'>
                <summary className='flex cursor-pointer list-none flex-wrap items-center gap-2 text-sm'>
                  <Icons.chevronRight className='h-3.5 w-3.5 transition-transform group-open:rotate-90' />
                  <span className='font-mono text-xs font-medium text-brand-navy'>{j.name}</span>
                  <span className='text-xs text-brand-muted'>{j.answers.join(' / ')}</span>
                </summary>
                <p className='mt-2 text-sm leading-relaxed text-brand-navy/80'>{j.rubric}</p>
              </details>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function AutoPoliciesPanel() {
  const [policies, setPolicies] = useState<AutoPolicy[] | null>(null)
  const [snapshot, setSnapshot] = useState<AutoPolicySnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    callsApi
      .autoPolicies()
      .then((r) => {
        setPolicies(r.items)
        setSnapshot(r.snapshot)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the policies.'))
  }, [])

  return (
    <div className='space-y-6'>
      {snapshot && (
        <div
          role={snapshot.stale ? 'alert' : 'status'}
          className={
            snapshot.stale
              ? 'rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900'
              : 'rounded-xl border border-black/[0.06] bg-slate-50 p-3 text-sm text-brand-muted'
          }
        >
          {snapshot.stale ? (
            <>
              This copy of the policies is {snapshot.age_days} days old (synced {snapshot.synced_at}). Check each policy in
              Supervity Auto before relying on it.
            </>
          ) : (
            <>
              A copy of the policies in {snapshot.source}, last synced {snapshot.synced_at}. Open a policy in Auto for the
              live version.
            </>
          )}
        </div>
      )}

      {error && (
        <div role='alert' className='rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700'>
          {error}
        </div>
      )}
      {policies === null && !error && (
        <div className='space-y-4'>
          <Skeleton className='h-64 w-full' />
          <Skeleton className='h-64 w-full' />
        </div>
      )}
      {policies?.map((p) => (
        <PolicyPanel key={p.policy_id} policy={p} />
      ))}
    </div>
  )
}
