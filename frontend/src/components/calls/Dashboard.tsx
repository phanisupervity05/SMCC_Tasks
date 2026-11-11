'use client'

// Dashboard summary for the calls home screen. Every number comes from /api/calls/stats.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Area,
  AreaChart,
} from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { CallsStats } from '@/lib/calls-api'

const BAND_COLORS = ['#DC2626', '#F97316', '#F59E0B', '#84CC16', '#10B981', '#059669']
const STATUS_COLORS: Record<string, string> = {
  done: '#10B981',
  sent_to_auto: '#5B8DEF',
  received: '#94A3B8',
  failed: '#DC2626',
}
const STATUS_LABELS: Record<string, string> = {
  done: 'Processed',
  sent_to_auto: 'Sent to Auto',
  received: 'Received',
  failed: 'Failed',
}
const AXIS = { fill: '#7B8AB8', fontSize: 11 }

function Kpi({
  label,
  value,
  hint,
  tone = 'text-brand-navy',
}: {
  label: string
  value: string | number
  hint?: string
  tone?: string
}) {
  return (
    <Card>
      <CardContent className='space-y-1 pt-5'>
        <p className='text-xs font-semibold uppercase tracking-wider text-brand-muted'>{label}</p>
        <p className={cn('font-display text-3xl font-bold', tone)}>{value}</p>
        {hint && <p className='text-xs text-brand-muted'>{hint}</p>}
      </CardContent>
    </Card>
  )
}

function ChartCard({
  title,
  description,
  children,
  className,
}: {
  title: string
  description?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <Card className={className}>
      <CardHeader className='pb-2'>
        <CardTitle className='text-base'>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

const Empty = () => (
  <div className='flex h-[220px] items-center justify-center text-sm text-brand-muted'>
    No data yet.
  </div>
)

export function CallsDashboard({ stats }: { stats: CallsStats | null }) {
  if (!stats) {
    return (
      <div className='space-y-4'>
        <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-5'>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className='h-28 w-full' />
          ))}
        </div>
        <div className='grid gap-4 lg:grid-cols-2'>
          <Skeleton className='h-72 w-full' />
          <Skeleton className='h-72 w-full' />
        </div>
      </div>
    )
  }

  const statusData = Object.entries(stats.by_status)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => ({ key: k, name: STATUS_LABELS[k] ?? k, value: n }))
  const bandData = stats.bands.map((b) => ({ name: `Band ${b.band}`, count: b.count, band: b.band }))
  const scored = bandData.some((b) => b.count > 0)
  const dayData = stats.per_day.map((d) => ({ ...d, label: d.date.slice(5) }))
  const pct = (n: number | null) => (n === null ? '-' : `${Math.round(n)}%`)

  return (
    <div className='space-y-4'>
      <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-5'>
        <Kpi label='Total calls' value={stats.total} hint={`${stats.in_progress} in progress`} />
        <Kpi
          label='Processed'
          value={stats.processed}
          hint={`Success rate ${pct(stats.success_rate)}`}
          tone='text-emerald-600'
        />
        <Kpi
          label='Failed'
          value={stats.failed}
          hint={stats.stuck ? `${stats.stuck} stuck in Auto` : 'Processing errors'}
          tone={stats.failed ? 'text-red-600' : 'text-brand-navy'}
        />
        <Kpi
          label='Rejected'
          value={stats.rejected}
          hint='Requests refused at intake'
          tone={stats.rejected ? 'text-amber-600' : 'text-brand-navy'}
        />
        <Kpi
          label='Avg audit score'
          value={pct(stats.avg_audit_percent)}
          hint={stats.avg_band === null ? 'No lead scores yet' : `Avg lead band ${stats.avg_band}`}
        />
      </div>

      <div className='grid gap-4 lg:grid-cols-2'>
        <ChartCard title='Lead band distribution' description='Number of calls in each lead band (0 to 5)'>
          {scored ? (
            <div className='h-[220px]'>
              <ResponsiveContainer width='100%' height='100%'>
                <BarChart data={bandData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray='3 3' stroke='rgba(20,26,66,0.06)' vertical={false} />
                  <XAxis dataKey='name' axisLine={false} tickLine={false} tick={AXIS} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={AXIS} />
                  <Tooltip cursor={{ fill: 'rgba(20,26,66,0.04)' }} />
                  <Bar dataKey='count' name='Calls' radius={[6, 6, 0, 0]}>
                    {bandData.map((b) => (
                      <Cell key={b.band} fill={BAND_COLORS[b.band]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Empty />
          )}
        </ChartCard>

        <ChartCard title='Status breakdown' description='Where every call currently stands'>
          {statusData.length ? (
            <div className='flex h-[220px] items-center gap-4'>
              <div className='h-full flex-1'>
                <ResponsiveContainer width='100%' height='100%'>
                  <PieChart>
                    <Pie data={statusData} dataKey='value' nameKey='name' innerRadius={50} outerRadius={85} paddingAngle={2}>
                      {statusData.map((s) => (
                        <Cell key={s.key} fill={STATUS_COLORS[s.key]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className='space-y-2 text-sm'>
                {statusData.map((s) => (
                  <li key={s.key} className='flex items-center gap-2'>
                    <span className='h-2.5 w-2.5 rounded-full' style={{ backgroundColor: STATUS_COLORS[s.key] }} />
                    <span className='text-brand-muted'>{s.name}</span>
                    <span className='font-semibold text-brand-navy'>{s.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <Empty />
          )}
        </ChartCard>

        <ChartCard title='Calls over time' description='Calls dropped per day, last 14 days'>
          <div className='h-[220px]'>
            <ResponsiveContainer width='100%' height='100%'>
              <AreaChart data={dayData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id='callsPerDay' x1='0' y1='0' x2='0' y2='1'>
                    <stop offset='0%' stopColor='#5B8DEF' stopOpacity={0.4} />
                    <stop offset='95%' stopColor='#5B8DEF' stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray='3 3' stroke='rgba(20,26,66,0.06)' vertical={false} />
                <XAxis dataKey='label' axisLine={false} tickLine={false} tick={AXIS} interval='preserveStartEnd' />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={AXIS} />
                <Tooltip />
                <Area type='monotone' dataKey='count' name='Calls' stroke='#5B8DEF' strokeWidth={2.5} fill='url(#callsPerDay)' />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <ChartCard title='Sales agents' description='Volume and quality per agent'>
          {stats.agents.length ? (
            <div className='max-h-[220px] overflow-auto'>
              <table className='w-full text-left text-sm'>
                <thead className='text-xs uppercase tracking-wider text-brand-muted'>
                  <tr>
                    <th className='pb-2 font-semibold'>Agent</th>
                    <th className='pb-2 font-semibold'>Calls</th>
                    <th className='pb-2 font-semibold'>Processed</th>
                    <th className='pb-2 font-semibold'>Avg band</th>
                    <th className='pb-2 font-semibold'>Avg audit</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.agents.map((a) => (
                    <tr key={a.agent_id} className='border-t border-black/[0.04]'>
                      <td className='py-2 font-medium text-brand-navy'>{a.agent_name}</td>
                      <td className='py-2'>{a.calls}</td>
                      <td className='py-2'>{a.done}</td>
                      <td className='py-2'>{a.avg_band ?? '-'}</td>
                      <td className='py-2'>{pct(a.avg_audit_percent)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty />
          )}
        </ChartCard>
      </div>
    </div>
  )
}
