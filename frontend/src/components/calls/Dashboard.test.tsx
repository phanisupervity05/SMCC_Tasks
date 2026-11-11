import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'

// Charts need real layout sizes, which jsdom does not have. Replace the chart container with a stub.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return { ...actual, ResponsiveContainer: () => <div data-testid='chart' /> }
})

import { CallsDashboard } from './Dashboard'
import type { CallsStats } from '@/lib/calls-api'

const stats: CallsStats = {
  total: 10,
  processed: 6,
  in_progress: 2,
  failed: 2,
  rejected: 3,
  stuck: 1,
  missing_lead_id: 0,
  success_rate: 60,
  avg_audit_percent: 72.4,
  avg_band: 3.2,
  by_status: { received: 1, sent_to_auto: 1, done: 6, failed: 2 },
  bands: [0, 1, 2, 3, 4, 5].map((band) => ({ band, count: band === 4 ? 3 : 0 })),
  per_day: [{ date: '2026-11-10', count: 4 }],
  agents: [
    { agent_id: 'A-1', agent_name: 'Asha', calls: 6, done: 5, avg_band: 4, avg_audit_percent: 80 },
    { agent_id: 'A-2', agent_name: 'Ben', calls: 4, done: 1, avg_band: null, avg_audit_percent: null },
  ],
}

// A label can also appear in a chart legend or table header; the KPI card comes first in the page.
const kpi = (label: string) => screen.getAllByText(label)[0].closest('div')!

describe('CallsDashboard', () => {
  it('shows skeletons, not numbers, while loading', () => {
    const { container } = render(<CallsDashboard stats={null} />)
    expect(screen.queryByText('Total calls')).not.toBeInTheDocument()
    expect(container.querySelectorAll('[class*="animate-shimmer"]').length).toBeGreaterThan(0)
  })

  it('shows the headline numbers from the stats', () => {
    render(<CallsDashboard stats={stats} />)
    expect(within(kpi('Total calls')).getByText('10')).toBeInTheDocument()
    expect(within(kpi('Processed')).getByText('6')).toBeInTheDocument()
    expect(within(kpi('Failed')).getByText('2')).toBeInTheDocument()
    expect(within(kpi('Rejected')).getByText('3')).toBeInTheDocument()
    expect(within(kpi('Avg audit score')).getByText('72%')).toBeInTheDocument()
    expect(screen.getByText(/success rate 60%/i)).toBeInTheDocument()
    expect(screen.getByText(/1 stuck in auto/i)).toBeInTheDocument()
  })

  it('lists each sales agent, with a dash where there is no score yet', () => {
    render(<CallsDashboard stats={stats} />)
    const ben = screen.getByText('Ben').closest('tr')!
    expect(within(ben).getAllByText('-').length).toBe(2)
    expect(within(screen.getByText('Asha').closest('tr')!).getByText('80%')).toBeInTheDocument()
  })

  it('says there is no data instead of drawing an empty band chart', () => {
    const empty = { ...stats, bands: stats.bands.map((b) => ({ ...b, count: 0 })), agents: [] }
    render(<CallsDashboard stats={empty} />)
    expect(screen.getAllByText('No data yet.').length).toBeGreaterThanOrEqual(2)
  })

  it('warns about calls saved without a Lead ID only when there are some', () => {
    const { rerender } = render(<CallsDashboard stats={stats} />)
    expect(screen.queryByText(/no lead id/i)).not.toBeInTheDocument()
    rerender(<CallsDashboard stats={{ ...stats, missing_lead_id: 2 }} />)
    expect(screen.getByText(/2 calls have no lead id/i)).toBeInTheDocument()
  })
})
