// frontend/src/lib/auth/dev-mock.ts
//
// =============================================================================
// DEV-ONLY MOCK LOGIN. NOT FOR PRODUCTION.
// =============================================================================
// Stands in for Keycloak SSO while no realm is available. It exists only when
// DEV_AUTH_ENABLED=true AND APP_ENV is not "production", and it needs both
// DEV_AUTH_SECRET and DEV_AUTH_PASSWORD to be set.
//
// It signs a token the backend's dev_mock provider (app/auth/dev_mock_provider.py)
// accepts:  devmock.<base64url(claims json)>.<hex hmac-sha256>
//
// To remove: delete this file, its use in api/auth/[...nextauth]/route.ts, and
// the "dev sign-in" block in app/auth/signin/page.tsx.
// =============================================================================
import CredentialsProvider from 'next-auth/providers/credentials'
import { createHmac, timingSafeEqual } from 'crypto'

export const DEV_MOCK_PROVIDER_ID = 'dev-mock'
const SESSION_HOURS = 8

export function devMockEnabled(): boolean {
  return (
    process.env.DEV_AUTH_ENABLED === 'true' &&
    (process.env.APP_ENV || 'development').toLowerCase() !== 'production' &&
    !!process.env.DEV_AUTH_SECRET &&
    !!process.env.DEV_AUTH_PASSWORD
  )
}

function sameString(a: string, b: string): boolean {
  const x = Buffer.from(a)
  const y = Buffer.from(b)
  return x.length === y.length && timingSafeEqual(x, y)
}

function signToken(username: string): string {
  const roles = (process.env.DEV_AUTH_ROLES || 'user')
    .split(',')
    .map((r) => r.trim())
    .filter(Boolean)
  const claims = {
    sub: `dev-${username}`,
    preferred_username: username,
    email: `${username}@dev.local`,
    name: username,
    realm_access: { roles },
    exp: Math.floor(Date.now() / 1000) + SESSION_HOURS * 3600,
  }
  const payload = Buffer.from(JSON.stringify(claims)).toString('base64url')
  const sig = createHmac('sha256', process.env.DEV_AUTH_SECRET as string)
    .update(payload)
    .digest('hex')
  return `devmock.${payload}.${sig}`
}

/** Returns the credentials provider, or an empty list when the dev flag is off. */
export function devMockProviders() {
  if (!devMockEnabled()) return []
  return [
    CredentialsProvider({
      id: DEV_MOCK_PROVIDER_ID,
      name: 'Dev mock login',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const username = (credentials?.username || '').trim()
        const password = credentials?.password || ''
        if (!/^[A-Za-z0-9._-]{1,64}$/.test(username)) return null
        if (!sameString(password, process.env.DEV_AUTH_PASSWORD as string)) return null
        return {
          id: `dev-${username}`,
          name: username,
          email: `${username}@dev.local`,
          accessToken: signToken(username),
        }
      },
    }),
  ]
}
