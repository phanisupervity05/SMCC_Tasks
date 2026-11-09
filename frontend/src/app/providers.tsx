'use client'

import { SessionProvider } from 'next-auth/react'
import { ToastProvider } from '@/components/ui/toast'
import { CommandPalette } from '@/components/CommandPalette'
import { AIProvider } from '@/context/AIContext'
import { AIManager } from '@/components/ai/AIManager'

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider
      basePath={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/api/auth`}
      // Refetch session every 4 minutes to keep tokens fresh
      // This triggers the JWT callback which handles token refresh
      refetchInterval={4 * 60}
      // Also refetch when user returns to the tab
      refetchOnWindowFocus={true}
    >
      <AIProvider>
      {children}
      <ToastProvider />
      <CommandPalette />
        <AIManager />
      </AIProvider>
    </SessionProvider>
  )
}
