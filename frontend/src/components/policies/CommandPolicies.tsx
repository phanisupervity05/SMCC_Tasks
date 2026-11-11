'use client'

// The Command Center policies: the rules this app enforces on every call.
import { useCallback, useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Icons } from '@/components/ui/icons'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { policiesApi, type CommandPolicy, type PolicyCatalog } from '@/lib/policies-api'
import { PolicyBuilderDialog } from './PolicyBuilderDialog'

const chip = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset'

export function CommandPolicies() {
  const [policies, setPolicies] = useState<CommandPolicy[] | null>(null)
  const [catalog, setCatalog] = useState<PolicyCatalog | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [builderOpen, setBuilderOpen] = useState(false)
  const [editing, setEditing] = useState<CommandPolicy | null>(null)
  const [deleting, setDeleting] = useState<CommandPolicy | null>(null)

  // keepError: reload the list after a failed change without wiping the message that explains the failure.
  const load = useCallback(async (keepError = false) => {
    try {
      const [list, cat] = await Promise.all([policiesApi.list(), catalog ? Promise.resolve(catalog) : policiesApi.catalog()])
      setPolicies(list.items)
      setCatalog(cat)
      if (!keepError) setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load the policies.')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openNew = () => {
    setEditing(null)
    setBuilderOpen(true)
  }
  const openEdit = (p: CommandPolicy) => {
    setEditing(p)
    setBuilderOpen(true)
  }

  const toggle = async (p: CommandPolicy, enabled: boolean) => {
    setPolicies((all) => all && all.map((x) => (x.id === p.id ? { ...x, enabled } : x))) // show it at once
    let failed = false
    try {
      await policiesApi.setEnabled(p.id, enabled)
    } catch (e) {
      failed = true
      setError(e instanceof Error ? e.message : 'Could not change the policy.')
    }
    load(failed)
  }

  const confirmDelete = async () => {
    if (!deleting) return
    let failed = false
    try {
      await policiesApi.remove(deleting.id)
    } catch (e) {
      failed = true
      setError(e instanceof Error ? e.message : 'Could not delete the policy.')
    }
    setDeleting(null)
    load(failed)
  }

  return (
    <div className='space-y-4'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <p className='max-w-2xl text-sm text-brand-muted'>
          Rules this Command Center enforces itself, on the drop form, the inbound webhook and finished calls. They are
          separate from the Supervity Auto policies that score each call.
        </p>
        <Button onClick={openNew} disabled={!catalog}>
          <Icons.plus className='mr-2 h-4 w-4' />
          New policy
        </Button>
      </div>

      {error && (
        <div role='alert' className='rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700'>
          {error}
        </div>
      )}

      {policies === null && !error && <Skeleton className='h-40 w-full' />}

      {policies?.length === 0 && (
        <Card>
          <CardContent className='py-12 text-center'>
            <p className='font-medium text-brand-navy'>No policies yet</p>
            <p className='mx-auto mt-1 max-w-md text-sm text-brand-muted'>
              Create one, for example to flag a duplicate Lead ID or reject a Lead ID in the wrong format. You can start
              from a template or describe the rule in plain English.
            </p>
            <Button className='mt-4' onClick={openNew} disabled={!catalog}>
              <Icons.plus className='mr-2 h-4 w-4' />
              New policy
            </Button>
          </CardContent>
        </Card>
      )}

      {policies?.map((p) => (
        <Card key={p.id} className={p.enabled ? '' : 'opacity-70'}>
          <CardContent className='space-y-3 pt-5'>
            <div className='flex flex-wrap items-start justify-between gap-3'>
              <div className='space-y-2'>
                <h3 className='text-base font-semibold text-brand-navy'>{p.name}</h3>
                <div className='flex flex-wrap gap-1.5'>
                  <span className={`${chip} bg-blue-50 text-blue-700 ring-blue-200`}>
                    {p.stage === 'intake' ? 'At intake' : 'After results'}
                  </span>
                  <span
                    className={`${chip} ${
                      p.action === 'reject' ? 'bg-red-50 text-red-700 ring-red-200' : 'bg-amber-50 text-amber-800 ring-amber-200'
                    }`}
                  >
                    {p.action === 'reject' ? 'Rejects' : 'Flags for review'}
                  </span>
                  {p.source === 'ai' && <span className={`${chip} bg-purple-50 text-purple-700 ring-purple-200`}>Drafted with AI</span>}
                  <span className={`${chip} bg-slate-50 text-slate-600 ring-slate-200`}>
                    Matched {p.hit_count} {p.hit_count === 1 ? 'time' : 'times'}
                  </span>
                </div>
              </div>
              <div className='flex items-center gap-2'>
                <div className='flex items-center gap-2 text-sm text-brand-muted'>
                  <Switch aria-label={`${p.enabled ? 'Disable' : 'Enable'} ${p.name}`} checked={p.enabled} onCheckedChange={(v) => toggle(p, v)} />
                  {p.enabled ? 'On' : 'Off'}
                </div>
                <Button variant='outline' size='sm' aria-label={`Edit ${p.name}`} onClick={() => openEdit(p)}>
                  <Icons.pencil className='h-4 w-4' />
                </Button>
                <Button variant='outline' size='sm' aria-label={`Delete ${p.name}`} onClick={() => setDeleting(p)}>
                  <Icons.trash className='h-4 w-4' />
                </Button>
              </div>
            </div>

            {p.description && <p className='text-sm text-brand-muted'>{p.description}</p>}

            <div>
              <p className='text-xs font-semibold uppercase tracking-wider text-brand-muted'>
                When {p.match_mode === 'all' ? 'all' : 'any'} of these is true
              </p>
              <ul className='mt-1 list-disc pl-5 text-sm text-brand-navy'>
                {p.summary.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </div>
            <p className='text-xs text-brand-muted'>
              Shown as: &ldquo;{p.effective_message}&rdquo;
              {p.updated_by ? ` · Last changed by ${p.updated_by}` : ''}
            </p>
          </CardContent>
        </Card>
      ))}

      {catalog && (
        <PolicyBuilderDialog open={builderOpen} onOpenChange={setBuilderOpen} catalog={catalog} initial={editing} onSaved={() => load()} />
      )}

      <AlertDialog open={deleting !== null} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this policy?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{deleting?.name}&rdquo; will stop being applied to new calls. Calls it already flagged keep their flags.
              This cannot be undone. To pause it instead, switch it off.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep it</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete policy</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
