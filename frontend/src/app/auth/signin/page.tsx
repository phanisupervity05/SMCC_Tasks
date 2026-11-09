'use client'

import { getProviders, signIn } from 'next-auth/react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Suspense, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Icons } from '@/components/ui/icons'
import { Logomark } from '@/components/brand'

// Errors that indicate stale cookies that should be auto-cleared
const AUTO_CLEAR_ERRORS = [
  'OAuthSignin',
  'OAuthCallback',
  'OAuthCreateAccount',
  'Callback',
]

function clearAuthCookies() {
  // List of all NextAuth cookies to clear
  const cookiesToClear = [
    'next-auth.session-token',
    '__Secure-next-auth.session-token',
    'next-auth.csrf-token',
    '__Secure-next-auth.csrf-token',
    'next-auth.callback-url',
    '__Secure-next-auth.callback-url',
    'next-auth.pkce.code_verifier',
    '__Secure-next-auth.pkce.code_verifier',
    'next-auth.state',
    '__Secure-next-auth.state',
  ]

  // Clear each cookie by setting it to expire immediately
  cookiesToClear.forEach((cookieName) => {
    // Clear for all possible paths
    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=${window.location.hostname}`
  })

  console.log('[AUTH] Automatically cleared stale auth cookies')
}

function SignInContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const callbackUrl = searchParams.get('callbackUrl') || '/'
  const error = searchParams.get('error')
  const [isClearing, setIsClearing] = useState(false)

  // DEV ONLY: the mock login exists only when the server was started with DEV_AUTH_ENABLED=true.
  const [devEnabled, setDevEnabled] = useState(false)
  const [devUser, setDevUser] = useState('')
  const [devPass, setDevPass] = useState('')
  useEffect(() => {
    getProviders()
      .then((p) => setDevEnabled(!!p?.['dev-mock']))
      .catch(() => setDevEnabled(false))
  }, [])

  // Auto-clear cookies on OAuth errors and redirect to clean sign-in
  useEffect(() => {
    if (error && AUTO_CLEAR_ERRORS.includes(error)) {
      setIsClearing(true)
      clearAuthCookies()

      // Small delay to ensure cookies are cleared, then redirect to clean URL
      const timer = setTimeout(() => {
        // Remove the error from URL and reload with clean state
        const cleanUrl = new URL(window.location.href)
        cleanUrl.searchParams.delete('error')
        router.replace(cleanUrl.pathname + cleanUrl.search)
        setIsClearing(false)
      }, 500)

      return () => clearTimeout(timer)
    }
  }, [error, router])

  // Show loading state while clearing cookies
  if (isClearing) {
    return (
      <div className='flex min-h-screen flex-col items-center justify-center bg-background gap-4'>
        <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
        <p className='text-sm text-muted-foreground'>Clearing session...</p>
      </div>
    )
  }

  const getErrorMessage = (errorCode: string | null) => {
    switch (errorCode) {
      case 'AccessDenied':
        return 'You do not have permission to access this resource.'
      case 'Verification':
        return 'The verification link has expired or has already been used.'
      case 'SessionRequired':
        return 'Please sign in to access this page.'
      case 'CredentialsSignin':
        return 'Wrong username or password.'
      default:
        // OAuth errors are auto-cleared, so we shouldn't see them here
        return errorCode ? 'An unexpected error occurred. Please try again.' : null
    }
  }

  const errorMessage = getErrorMessage(error)

  return (
    <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className='w-full max-w-md'
      >
        <Card className='relative overflow-hidden bg-white shadow-float-lg transition-shadow duration-500 hover:shadow-accent'>
          <CardWatermark opacity={4} scale={1} />
          <CardHeader className='relative z-10 space-y-4 pb-8 text-center'>
            <motion.div
              className='mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-navy shadow-xl'
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{
                delay: 0.2,
                type: 'spring',
                stiffness: 200,
                damping: 15,
              }}
            >
              <Logomark variant='light' size={48} />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <CardTitle className='text-display-5 font-bold text-brand-navy'>
                Supervity
              </CardTitle>
              <p className='mt-2 text-muted-foreground'>
                Command Center Access
              </p>
            </motion.div>
          </CardHeader>
          <CardContent className='relative z-10 space-y-4 px-8 pb-8'>
            {/* Error Message (only for non-auto-cleared errors) */}
            {errorMessage && (
              <motion.div
                className='rounded-lg border border-red-200 bg-red-50 p-4 text-center text-sm text-red-700'
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <p>{errorMessage}</p>
              </motion.div>
            )}

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.4 }}
            >
              <Button
                onClick={() => signIn('keycloak', { callbackUrl })}
                variant='gradient'
                size='lg'
                className='group w-full py-6 text-base'
              >
                Sign In with SSO
                <Icons.arrowRight className='ml-2 h-4 w-4 transition-transform duration-200 group-hover:translate-x-1' />
              </Button>
            </motion.div>

            {/* ---- DEV ONLY: mock login. Remove with lib/auth/dev-mock.ts ---- */}
            {devEnabled && (
              <form
                className='space-y-3 rounded-xl border border-dashed border-amber-300 bg-amber-50/60 p-4'
                onSubmit={(e) => {
                  e.preventDefault()
                  signIn('dev-mock', {
                    username: devUser,
                    password: devPass,
                    callbackUrl,
                  })
                }}
              >
                <p className='text-xs font-semibold uppercase tracking-wider text-amber-700'>
                  Dev only: mock login
                </p>
                <Input
                  placeholder='Username'
                  value={devUser}
                  onChange={(e) => setDevUser(e.target.value)}
                  autoComplete='username'
                />
                <Input
                  type='password'
                  placeholder='Password'
                  value={devPass}
                  onChange={(e) => setDevPass(e.target.value)}
                  autoComplete='current-password'
                />
                <Button type='submit' variant='outline' className='w-full'>
                  Sign in (dev)
                </Button>
              </form>
            )}
            {/* ---- end dev only ---- */}

            <motion.p
              className='text-center text-xs text-muted-foreground'
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5, duration: 0.4 }}
            >
              Use your organization credentials to sign in
            </motion.p>

            <motion.div
              className='pt-4 text-center'
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6, duration: 0.4 }}
            >
              <p className='text-sm text-muted-foreground'>
                Don&apos;t have an account?{' '}
                <a
                  href={`${process.env.NEXT_PUBLIC_BASE_PATH || ''}/auth/register`}
                  className='font-medium text-brand-cornflower hover:text-brand-navy transition-colors'
                >
                  Register here
                </a>
              </p>
            </motion.div>
          </CardContent>
        </Card>
    </motion.div>
  )
}

export default function SignInPage() {
  return (
    <Suspense
      fallback={
        <div className='flex min-h-screen items-center justify-center bg-background'>
          <div className='h-8 w-8 animate-spin rounded-full border-4 border-brand-navy border-t-transparent' />
        </div>
      }
    >
      <SignInContent />
    </Suspense>
  )
}

