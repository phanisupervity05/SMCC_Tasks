'use client'

// Create or edit a Command Center policy: rule builder, plain-English drafting with AI, and a dry-run test.
// Nothing is decided here: the backend validates every policy and enforces every rule.
import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Icons } from '@/components/ui/icons'
import { ApiError, type ApiFieldError } from '@/lib/api-client'
import {
  policiesApi,
  type CatalogField,
  type CommandPolicy,
  type PolicyAction,
  type PolicyCatalog,
  type PolicyInput,
  type PolicyTestResult,
  type MatchMode,
  type Stage,
} from '@/lib/policies-api'

interface Row {
  field: string
  operator: string
  value: string
}

interface Form {
  name: string
  description: string
  stage: Stage
  action: PolicyAction
  match_mode: MatchMode
  message: string
  enabled: boolean
  rows: Row[]
  source: 'builder' | 'ai'
  natural_language: string
}

const selectClass =
  'h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cornflower'

const VALUE_HINT: Record<string, string> = {
  in_list: 'a.com, b.com',
  not_in_list: 'a.com, b.com',
  matches_format: 'LEAD-####  (# digit, A letter, * anything)',
  not_matches_format: 'LEAD-####  (# digit, A letter, * anything)',
}

function fieldsFor(catalog: PolicyCatalog, stage: Stage): CatalogField[] {
  return catalog.fields.filter((f) => f.stages.includes(stage))
}

function emptyRow(catalog: PolicyCatalog, stage: Stage): Row {
  const f = fieldsFor(catalog, stage)[0]
  return { field: f.key, operator: f.operators[0].value, value: '' }
}

function fromInput(catalog: PolicyCatalog, p: PolicyInput): Form {
  return {
    name: p.name ?? '',
    description: p.description ?? '',
    stage: p.stage,
    action: p.action,
    match_mode: p.match_mode,
    message: p.message ?? '',
    enabled: p.enabled ?? true,
    rows: p.conditions.length
      ? p.conditions.map((c) => ({ field: c.field, operator: c.operator, value: c.value === null ? '' : String(c.value) }))
      : [emptyRow(catalog, p.stage)],
    source: p.source ?? 'builder',
    natural_language: p.natural_language ?? '',
  }
}

function blankForm(catalog: PolicyCatalog): Form {
  return {
    name: '', description: '', stage: 'intake', action: 'flag', match_mode: 'all', message: '', enabled: true,
    rows: [emptyRow(catalog, 'intake')], source: 'builder', natural_language: '',
  }
}

export function PolicyBuilderDialog({
  open,
  onOpenChange,
  catalog,
  initial,
  onSaved,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  catalog: PolicyCatalog
  initial: CommandPolicy | null
  onSaved: () => void
}) {
  const [form, setForm] = useState<Form>(() => blankForm(catalog))
  const [errors, setErrors] = useState<ApiFieldError[]>([])
  const [saving, setSaving] = useState(false)
  const [aiText, setAiText] = useState('')
  const [aiBusy, setAiBusy] = useState(false)
  const [aiNote, setAiNote] = useState<{ ok: boolean; text: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<PolicyTestResult | null>(null)

  // Start fresh each time the dialog opens.
  useEffect(() => {
    if (!open) return
    setForm(initial ? fromInput(catalog, initial) : blankForm(catalog))
    setErrors([])
    setAiText('')
    setAiNote(null)
    setTestResult(null)
  }, [open, initial, catalog])

  const fieldByKey = useMemo(() => new Map(catalog.fields.map((f) => [f.key, f])), [catalog])
  const stageFields = fieldsFor(catalog, form.stage)
  const groups = useMemo(() => {
    const g = new Map<string, CatalogField[]>()
    stageFields.forEach((f) => g.set(f.group, [...(g.get(f.group) ?? []), f]))
    return [...g.entries()]
  }, [stageFields])

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }))
  const setRow = (i: number, patch: Partial<Row>) =>
    setForm((f) => ({ ...f, rows: f.rows.map((r, j) => (j === i ? { ...r, ...patch } : r)) }))

  const changeStage = (stage: Stage) =>
    setForm((f) => ({
      ...f,
      stage,
      // After results a policy can only flag, and fields only known later are not available at intake.
      action: stage === 'results' ? 'flag' : f.action,
      rows: f.rows.map((r) => (fieldByKey.get(r.field)?.stages.includes(stage) ? r : emptyRow(catalog, stage))),
    }))

  const changeField = (i: number, key: string) => {
    const f = fieldByKey.get(key)!
    setRow(i, { field: key, operator: f.operators[0].value, value: '' })
  }

  const toInput = (): PolicyInput => ({
    name: form.name,
    description: form.description || null,
    stage: form.stage,
    action: form.action,
    match_mode: form.match_mode,
    message: form.message || null,
    enabled: form.enabled,
    source: form.source,
    natural_language: form.source === 'ai' ? form.natural_language : null,
    conditions: form.rows.map((r) => {
      const op = fieldByKey.get(r.field)?.operators.find((o) => o.value === r.operator)
      return { field: r.field, operator: r.operator, value: op?.needs_value === false ? null : r.value }
    }),
  })

  const errFor = (path: string) => errors.find((e) => e.field === path)?.message
  const known = new Set(['name', 'description', 'message', 'stage', 'action', 'match_mode', 'conditions'])
  const otherErrors = errors.filter((e) => !known.has(e.field) && !e.field.startsWith('conditions['))

  const readErrors = (err: unknown) => {
    if (err instanceof ApiError && err.fieldErrors?.length) setErrors(err.fieldErrors)
    else setErrors([{ field: 'form', message: err instanceof Error ? err.message : 'Something went wrong.' }])
  }

  const save = async () => {
    setSaving(true)
    setErrors([])
    try {
      if (initial) await policiesApi.update(initial.id, toInput())
      else await policiesApi.create(toInput())
      onSaved()
      onOpenChange(false)
    } catch (err) {
      readErrors(err)
    } finally {
      setSaving(false)
    }
  }

  const runTest = async () => {
    setTesting(true)
    setErrors([])
    setTestResult(null)
    try {
      setTestResult(await policiesApi.test(toInput()))
    } catch (err) {
      readErrors(err)
    } finally {
      setTesting(false)
    }
  }

  const draftWithAi = async () => {
    setAiBusy(true)
    setAiNote(null)
    try {
      const { draft } = await policiesApi.fromText(aiText)
      setForm(fromInput(catalog, draft))
      setErrors([])
      setTestResult(null)
      setAiNote({ ok: true, text: 'Draft ready. Check every part below, then save. It is switched off until you turn it on.' })
    } catch (err) {
      setAiNote({ ok: false, text: err instanceof Error ? err.message : 'Could not draft the policy.' })
    } finally {
      setAiBusy(false)
    }
  }

  const applyTemplate = (id: string) => {
    const t = catalog.templates.find((x) => x.id === id)
    if (t) {
      setForm(fromInput(catalog, t.policy))
      setErrors([])
      setTestResult(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-h-[90vh] max-w-3xl overflow-y-auto'>
        <DialogHeader>
          <DialogTitle>{initial ? 'Edit policy' : 'New policy'}</DialogTitle>
          <DialogDescription>
            A policy checks every call and either flags it for review or, at intake, rejects it.
          </DialogDescription>
        </DialogHeader>

        {!initial && (
          <div className='space-y-3 rounded-xl border border-brand-cornflower/30 bg-brand-cornflower/5 p-4'>
            <div className='flex items-center gap-2 text-sm font-semibold text-brand-navy'>
              <Icons.sparkles className='h-4 w-4' /> Describe it in plain English
            </div>
            <textarea
              aria-label='Describe the policy'
              value={aiText}
              onChange={(e) => setAiText(e.target.value)}
              maxLength={1000}
              rows={2}
              placeholder='For example: Flag any call whose Lead ID was already used on another call'
              className='w-full rounded-lg border border-gray-200 bg-white p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cornflower'
            />
            <div className='flex flex-wrap items-center gap-3'>
              <Button type='button' size='sm' onClick={draftWithAi} disabled={aiBusy || aiText.trim().length < 8}>
                {aiBusy ? 'Drafting...' : 'Draft with AI'}
              </Button>
              <select aria-label='Start from a template' className={`${selectClass} w-auto`} value='' onChange={(e) => applyTemplate(e.target.value)}>
                <option value=''>Or start from a template...</option>
                {catalog.templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>
            </div>
            {aiNote && (
              <p role={aiNote.ok ? 'status' : 'alert'} className={aiNote.ok ? 'text-sm text-emerald-700' : 'text-sm text-red-700'}>
                {aiNote.text}
              </p>
            )}
          </div>
        )}

        <div className='grid gap-4 sm:grid-cols-2'>
          <div className='space-y-1 sm:col-span-2'>
            <label htmlFor='policy-name' className='text-sm font-medium text-brand-navy'>Name</label>
            <Input id='policy-name' value={form.name} onChange={(e) => set('name', e.target.value)} />
            {errFor('name') && <p className='text-xs text-red-700'>{errFor('name')}</p>}
          </div>
          <div className='space-y-1 sm:col-span-2'>
            <label htmlFor='policy-description' className='text-sm font-medium text-brand-navy'>Description (optional)</label>
            <Input id='policy-description' value={form.description} onChange={(e) => set('description', e.target.value)} />
            {errFor('description') && <p className='text-xs text-red-700'>{errFor('description')}</p>}
          </div>
          <div className='space-y-1'>
            <label htmlFor='policy-stage' className='text-sm font-medium text-brand-navy'>When does it run?</label>
            <select id='policy-stage' className={selectClass} value={form.stage} onChange={(e) => changeStage(e.target.value as Stage)}>
              {catalog.stages.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div className='space-y-1'>
            <label htmlFor='policy-action' className='text-sm font-medium text-brand-navy'>What happens on a match?</label>
            <select id='policy-action' className={selectClass} value={form.action} onChange={(e) => set('action', e.target.value as PolicyAction)}>
              {catalog.actions.map((a) => (
                <option key={a.value} value={a.value} disabled={a.value === 'reject' && form.stage === 'results'}>
                  {a.label}
                </option>
              ))}
            </select>
            {errFor('action') && <p className='text-xs text-red-700'>{errFor('action')}</p>}
          </div>
        </div>

        <div className='space-y-3'>
          <div className='flex flex-wrap items-center gap-3'>
            <h3 className='text-sm font-semibold text-brand-navy'>Conditions</h3>
            <select aria-label='Match' className={`${selectClass} w-auto`} value={form.match_mode} onChange={(e) => set('match_mode', e.target.value as MatchMode)}>
              {catalog.match_modes.map((m) => (
                <option key={m.value} value={m.value}>Match: {m.label.toLowerCase()}</option>
              ))}
            </select>
          </div>
          {errFor('conditions') && <p className='text-xs text-red-700'>{errFor('conditions')}</p>}

          {form.rows.map((row, i) => {
            const spec = fieldByKey.get(row.field)
            const op = spec?.operators.find((o) => o.value === row.operator)
            const valueError = errFor(`conditions[${i}].value`)
            const otherError = errFor(`conditions[${i}].field`) ?? errFor(`conditions[${i}].operator`) ?? errFor(`conditions[${i}]`)
            return (
              <div key={i} className='space-y-1 rounded-lg border border-black/[0.06] p-3'>
                <div className='grid gap-2 sm:grid-cols-[1.4fr_1fr_1fr_auto]'>
                  <select aria-label={`Condition ${i + 1} field`} className={selectClass} value={row.field} onChange={(e) => changeField(i, e.target.value)}>
                    {groups.map(([group, fields]) => (
                      <optgroup key={group} label={group}>
                        {fields.map((f) => (
                          <option key={f.key} value={f.key}>{f.label}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  <select aria-label={`Condition ${i + 1} operator`} className={selectClass} value={row.operator} onChange={(e) => setRow(i, { operator: e.target.value })}>
                    {spec?.operators.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                  {op?.needs_value === false ? (
                    <span className='self-center text-sm text-brand-muted'>no value needed</span>
                  ) : (
                    <Input
                      aria-label={`Condition ${i + 1} value`}
                      type={spec?.type === 'number' ? 'number' : 'text'}
                      step='any'
                      value={row.value}
                      placeholder={VALUE_HINT[row.operator] ?? ''}
                      onChange={(e) => setRow(i, { value: e.target.value })}
                    />
                  )}
                  <Button
                    type='button'
                    variant='ghost'
                    size='sm'
                    aria-label={`Remove condition ${i + 1}`}
                    disabled={form.rows.length === 1}
                    onClick={() => setForm((f) => ({ ...f, rows: f.rows.filter((_, j) => j !== i) }))}
                  >
                    <Icons.trash className='h-4 w-4' />
                  </Button>
                </div>
                {spec?.help && <p className='text-xs text-brand-muted'>{spec.help}</p>}
                {(valueError || otherError) && <p className='text-xs text-red-700'>{valueError ?? otherError}</p>}
              </div>
            )
          })}
          <Button
            type='button'
            variant='outline'
            size='sm'
            disabled={form.rows.length >= 10}
            onClick={() => setForm((f) => ({ ...f, rows: [...f.rows, emptyRow(catalog, f.stage)] }))}
          >
            <Icons.plus className='mr-1 h-4 w-4' /> Add condition
          </Button>
        </div>

        <div className='space-y-1'>
          <label htmlFor='policy-message' className='text-sm font-medium text-brand-navy'>
            Message shown on a match (optional)
          </label>
          <Input id='policy-message' value={form.message} onChange={(e) => set('message', e.target.value)} placeholder='Leave empty to describe the conditions automatically' />
          {errFor('message') && <p className='text-xs text-red-700'>{errFor('message')}</p>}
        </div>

        <div className='flex items-center gap-3'>
          <Switch id='policy-enabled' checked={form.enabled} onCheckedChange={(v) => set('enabled', v)} />
          <label htmlFor='policy-enabled' className='text-sm text-brand-navy'>Enabled (the policy is applied to calls)</label>
        </div>

        {otherErrors.length > 0 && (
          <div role='alert' className='rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700'>
            {otherErrors.map((e, i) => (
              <p key={i}>{e.message}</p>
            ))}
          </div>
        )}

        {testResult && (
          <div role='status' className='rounded-lg border border-black/[0.06] bg-slate-50 p-3 text-sm text-brand-navy'>
            <p className='font-medium'>
              Would match {testResult.matched} of the last {testResult.checked} calls.
            </p>
            {testResult.examples.length > 0 && (
              <ul className='mt-1 list-disc pl-5 text-xs text-brand-muted'>
                {testResult.examples.map((e) => (
                  <li key={e.task_id}>
                    {e.task_id} ({e.agent_name}
                    {e.lead_id ? `, Lead ${e.lead_id}` : ''})
                  </li>
                ))}
              </ul>
            )}
            <p className='mt-1 text-xs text-brand-muted'>This was a test only. Nothing was flagged or saved.</p>
          </div>
        )}

        <DialogFooter className='gap-2 sm:gap-0'>
          <Button type='button' variant='ghost' onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type='button' variant='outline' onClick={runTest} disabled={testing}>
            {testing ? 'Testing...' : 'Test on recent calls'}
          </Button>
          <Button type='button' onClick={save} disabled={saving}>
            {saving ? 'Saving...' : initial ? 'Save changes' : 'Create policy'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
