'use client'

// Policies: the rules the Command Center enforces itself, and the two Supervity Auto policies that score each call.
import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'
import { CommandPolicies } from '@/components/policies/CommandPolicies'
import { AutoPoliciesPanel } from '@/components/policies/AutoPoliciesPanel'

const TABS = [
  { id: 'command', label: 'Command Center policies', Icon: Icons.shield },
  { id: 'auto', label: 'Auto policies (call agent)', Icon: Icons.brain },
] as const

export default function PoliciesPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]['id']>('command')

  return (
    <div className='space-y-6'>
      <div>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>Policies</h1>
        <p className='mt-1 text-brand-muted'>
          Rules that check every sales call: the ones this Command Center enforces, and the Supervity Auto policies that score
          each call.
        </p>
      </div>

      <div role='tablist' className='flex gap-1 rounded-xl bg-gray-100 p-1.5'>
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            role='tab'
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
              tab === id ? 'bg-white text-brand-navy shadow-sm' : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Icon className='h-4 w-4' />
            {label}
          </button>
        ))}
      </div>

      {tab === 'command' ? <CommandPolicies /> : <AutoPoliciesPanel />}
    </div>
  )
}
