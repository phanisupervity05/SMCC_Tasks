'use client'

// Drop-call screen. Sends what the person typed; every rule is checked by the backend,
// and its errors are shown here as they come back.
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Icons } from '@/components/ui/icons'
import { toast } from '@/components/ui/toast'
import { ApiError, type ApiFieldError } from '@/lib/api-client'
import { callsApi, type CallsConfig } from '@/lib/calls-api'

const EMPTY = {
  recording_url: '',
  agent_id: '',
  agent_name: '',
  customer_name: '',
  lead_id: '',
  call_date: '',
}

function Field({
  id,
  label,
  required,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  required?: boolean
  hint?: string
  error?: string
  children: React.ReactNode
}) {
  return (
    <div className='space-y-1.5'>
      <Label htmlFor={id}>
        {label}
        {required && <span className='ml-0.5 text-red-600'>*</span>}
      </Label>
      {children}
      {hint && !error && <p className='text-xs text-brand-muted'>{hint}</p>}
      {error && (
        <p className='text-xs font-medium text-red-600' role='alert'>
          {error}
        </p>
      )}
    </div>
  )
}

export default function DropCallPage() {
  const router = useRouter()
  const [form, setForm] = useState(EMPTY)
  const [config, setConfig] = useState<CallsConfig | null>(null)
  const [scenario, setScenario] = useState('normal') // AUTO STUB
  const [source, setSource] = useState<'link' | 'file'>('link')
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<ApiFieldError[]>([])
  const [generalError, setGeneralError] = useState<string | null>(null)

  useEffect(() => {
    callsApi.config().then(setConfig).catch(() => setConfig(null))
  }, [])

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))
  const fieldError = (name: string) => errors.find((e) => e.field === name)?.message

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setErrors([])
    setGeneralError(null)
    // Send only what was filled in. The backend decides what is required.
    const body: Record<string, string> = {}
    for (const [k, v] of Object.entries(form)) if (v.trim()) body[k] = v.trim()
    // Both ways in end up as recording_url, so the rest of the drop is identical.
    if (source === 'file') {
      delete body.recording_url
      if (!file) {
        setErrors([{ field: 'audio_file', message: 'choose an audio file' }])
        setGeneralError('The backend rejected this call. Nothing was saved.')
        setBusy(false)
        return
      }
      try {
        body.recording_url = (await callsApi.uploadAudio(file)).url
      } catch (err) {
        if (err instanceof ApiError && err.fieldErrors?.length) setErrors(err.fieldErrors)
        setGeneralError(err instanceof Error ? err.message : 'Upload failed.')
        setBusy(false)
        return
      }
    }
    // AUTO STUB START
    if (config?.test_mode) body.stub_scenario = scenario
    // AUTO STUB END
    try {
      const res = await callsApi.drop(body)
      toast.success(
        res.created
          ? 'Call received.'
          : 'This call was already dropped. Showing the existing call.'
      )
      router.push(`/calls/${res.call.task_id}`)
    } catch (err) {
      if (err instanceof ApiError && err.fieldErrors?.length) {
        setErrors(err.fieldErrors)
        setGeneralError('The backend rejected this call. Nothing was saved.')
      } else {
        setGeneralError(err instanceof Error ? err.message : 'Something went wrong.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className='mx-auto w-full max-w-2xl space-y-6'>
      <div>
        <Link href='/' className='mb-3 inline-flex items-center text-sm text-brand-muted hover:text-brand-navy'>
          <Icons.arrowLeft className='mr-1 h-4 w-4' /> Calls
        </Link>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>Drop a call</h1>
        <p className='mt-1 text-brand-muted'>
          Paste a recording link or drop an audio file, and say who made the call. Dropping the same call twice gives the same
          call, not a second one.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Call details</CardTitle>
          <CardDescription>Fields marked * are required.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} noValidate className='space-y-5'>
            {generalError && (
              <div role='alert' className='rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700'>
                <p className='font-semibold'>{generalError}</p>
                {errors.length > 0 && (
                  <ul className='mt-1 list-disc pl-5'>
                    {errors.map((er, i) => (
                      <li key={i}>
                        <span className='font-mono text-xs'>{er.field}</span>: {er.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <div className='space-y-3'>
              <div role='tablist' aria-label='Recording source' className='inline-flex rounded-lg border p-1 text-sm'>
                {(['link', 'file'] as const).map((s) => (
                  <button
                    key={s}
                    type='button'
                    role='tab'
                    aria-selected={source === s}
                    onClick={() => setSource(s)}
                    className={`rounded-md px-3 py-1.5 font-medium ${
                      source === s ? 'bg-brand-navy text-white' : 'text-brand-muted hover:text-brand-navy'
                    }`}
                  >
                    {s === 'link' ? 'Paste a link' : 'Drop an audio file'}
                  </button>
                ))}
              </div>

              {source === 'link' ? (
                <Field id='recording_url' label='Recording link' required error={fieldError('recording_url')}>
                  <Input id='recording_url' placeholder='https://...' value={form.recording_url} onChange={set('recording_url')} />
                </Field>
              ) : (
                <Field
                  id='audio_file'
                  label='Audio file'
                  required
                  hint='mp3, wav, m4a, ogg, webm, aac or flac, up to 50 MB.'
                  error={fieldError('audio_file') ?? fieldError('recording_url')}
                >
                  <label
                    htmlFor='audio_file'
                    onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => {
                      e.preventDefault()
                      setDragging(false)
                      const f = e.dataTransfer.files?.[0]
                      if (f) setFile(f)
                    }}
                    className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed p-6 text-center text-sm ${
                      dragging ? 'border-brand-navy bg-brand-navy/5' : 'border-gray-300'
                    }`}
                  >
                    {file ? (
                      <span className='font-medium text-brand-navy'>
                        {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                      </span>
                    ) : (
                      <span className='text-brand-muted'>Drag an audio file here, or click to choose one</span>
                    )}
                    <input
                      id='audio_file'
                      type='file'
                      accept='audio/*,.mp3,.wav,.m4a,.ogg,.webm,.aac,.flac'
                      className='sr-only'
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </label>
                </Field>
              )}
            </div>

            <div className='grid gap-5 sm:grid-cols-2'>
              <Field id='agent_id' label='Sales agent ID' required error={fieldError('agent_id')}>
                <Input id='agent_id' value={form.agent_id} onChange={set('agent_id')} />
              </Field>
              <Field id='agent_name' label='Sales agent name' required error={fieldError('agent_name')}>
                <Input id='agent_name' value={form.agent_name} onChange={set('agent_name')} />
              </Field>
              <Field id='customer_name' label='Customer name' error={fieldError('customer_name')}>
                <Input id='customer_name' value={form.customer_name} onChange={set('customer_name')} />
              </Field>
              <Field id='lead_id' label='Lead ID' error={fieldError('lead_id')}>
                <Input id='lead_id' value={form.lead_id} onChange={set('lead_id')} />
              </Field>
              <Field
                id='call_date'
                label='Call date'
                hint='Part of the call identity: same link and date means the same call.'
                error={fieldError('call_date')}
              >
                <Input id='call_date' type='date' value={form.call_date} onChange={set('call_date')} />
              </Field>
            </div>

            {/* ---- AUTO STUB START: test mode only, delete with app/auto_stub/ ---- */}
            {config?.test_mode && (
              <div className='space-y-2 rounded-xl border border-dashed border-amber-300 bg-amber-50/60 p-4'>
                <p className='text-xs font-semibold uppercase tracking-wider text-amber-700'>
                  Test mode: what the fake Auto will send back
                </p>
                <Select value={scenario} onValueChange={setScenario}>
                  <SelectTrigger aria-label='Stub scenario'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {config.stub_scenarios.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {fieldError('stub_scenario') && (
                  <p className='text-xs font-medium text-red-600' role='alert'>
                    {fieldError('stub_scenario')}
                  </p>
                )}
              </div>
            )}
            {/* ---- AUTO STUB END ---- */}

            <div className='flex justify-end gap-2 pt-2'>
              <Button type='button' variant='outline' onClick={() => router.push('/')}>
                Cancel
              </Button>
              <Button type='submit' disabled={busy}>
                {busy && <Icons.loader className='mr-2 h-4 w-4 animate-spin' />}
                Drop call
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
