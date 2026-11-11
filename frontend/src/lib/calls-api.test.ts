import { describe, it, expect, vi, beforeEach } from 'vitest'

const get = vi.fn()
const download = vi.fn()
vi.mock('@/lib/api-client', () => ({
  default: vi.fn(),
  apiClient: { get: (...a: unknown[]) => get(...a), post: vi.fn(), patch: vi.fn() },
  apiClientDownload: (...a: unknown[]) => download(...a),
}))

import { callsApi, inProgress } from './calls-api'

describe('callsApi query strings', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ total: 0, items: [] })
    download.mockReset().mockResolvedValue({ blob: new Blob(), filename: 'x.csv' })
  })

  it('sends filters, dates and the page window to the list', async () => {
    await callsApi.list({ band: '4', agent_id: 'A-1', status: 'failed', date_from: '2026-11-01', date_to: '2026-11-10', limit: 25, offset: 50 })
    const url = new URL(get.mock.calls[0][0], 'http://x')
    expect(url.pathname).toBe('/api/calls')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      band: '4', agent_id: 'A-1', status: 'failed', date_from: '2026-11-01', date_to: '2026-11-10', limit: '25', offset: '50',
    })
  })

  it('asks only for flagged calls when the review filter is on', async () => {
    await callsApi.list({ flagged: true })
    expect(get.mock.calls[0][0]).toBe('/api/calls?flagged=true')
    get.mockClear()
    await callsApi.list({ flagged: false })
    expect(get.mock.calls[0][0]).toBe('/api/calls?')
  })

  it('leaves out filters that are not set', async () => {
    await callsApi.list({})
    expect(get.mock.calls[0][0]).toBe('/api/calls?')
  })

  it('sends only the date range to the stats, not the table filters', async () => {
    await callsApi.stats({ date_from: '2026-11-01' })
    expect(get.mock.calls[0][0]).toBe('/api/calls/stats?date_from=2026-11-01')
  })

  it('exports with the same filters but no paging', async () => {
    await callsApi.exportCsv({ status: 'done', date_to: '2026-11-10', limit: undefined, offset: undefined })
    expect(download.mock.calls[0][0]).toBe('/api/calls/export.csv?status=done&date_to=2026-11-10')
  })

  it('knows which statuses are still in progress', () => {
    expect(inProgress('received')).toBe(true)
    expect(inProgress('sent_to_auto')).toBe(true)
    expect(inProgress('done')).toBe(false)
    expect(inProgress('failed')).toBe(false)
  })
})
