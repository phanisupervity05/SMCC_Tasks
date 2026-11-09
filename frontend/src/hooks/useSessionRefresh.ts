'use client'

import { useSession, signIn } from 'next-auth/react'
import { useEffect } from 'react'

/**
 * Hook to monitor session health and handle token refresh errors
 * Automatically triggers re-authentication when refresh fails
 */
export function useSessionRefresh() {
  const { data: session, status } = useSession()

  useEffect(() => {
    // Check if there's a refresh error in the session
    if (session?.error === 'RefreshAccessTokenError') {
      console.log(
        '[Session] Token refresh failed. Triggering re-authentication...'
      )
      // Automatically sign in again to get fresh tokens
      signIn('keycloak')
    }
  }, [session?.error])

  return { session, status }
}

