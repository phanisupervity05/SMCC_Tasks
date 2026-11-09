// frontend/src/app/api/auth/[...nextauth]/route.ts
import NextAuth, { AuthOptions } from 'next-auth'
import KeycloakProvider from 'next-auth/providers/keycloak'
import { JWT } from 'next-auth/jwt'
import { DEV_MOCK_PROVIDER_ID, devMockProviders } from '@/lib/auth/dev-mock'

const isAuthDebug = process.env.SUPERVITY_AUTH_DEBUG === 'true'

function log(message: string, data?: object) {
  if (isAuthDebug) {
    const logData = data ? JSON.stringify(data, null, 2) : ''
    console.log(
      `[AUTH_DEBUG | NextAuth] ${new Date().toISOString()}: ${message}\n${logData}`
    )
  }
}

// Buffer time: refresh token 60 seconds before it expires
const TOKEN_REFRESH_BUFFER_SECONDS = 60

async function refreshAccessToken(token: JWT): Promise<JWT> {
  log('Access token has expired or is about to expire. Attempting to refresh.')
  try {
    // Keycloak is hosted on Google Cloud Run (external URL)
    // KEYCLOAK_SERVER_URL should be set to your Cloud Run URL
    // e.g., https://supervity-auth-xyz.a.run.app
    const keycloakServerUrl = process.env.KEYCLOAK_SERVER_URL
    const keycloakRealm = process.env.KEYCLOAK_REALM || 'supervity'

    if (!keycloakServerUrl) {
      throw new Error('KEYCLOAK_SERVER_URL environment variable is not set')
    }
    const response = await fetch(
      `${keycloakServerUrl}/realms/${keycloakRealm}/protocol/openid-connect/token`,
      {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        method: 'POST',
        body: new URLSearchParams({
          client_id: process.env.KEYCLOAK_CLIENT_ID!,
          client_secret: process.env.KEYCLOAK_CLIENT_SECRET!,
          grant_type: 'refresh_token',
          refresh_token: token.refreshToken as string,
        }),
      }
    )

    const refreshedTokens = await response.json()

    if (!response.ok) {
      log('🔴 Token refresh failed with response:', refreshedTokens)
      throw refreshedTokens
    }

    const expiresIn = Number(refreshedTokens.expires_in) || 300
    const newExpiry = Date.now() + expiresIn * 1000

    log('✅ Successfully refreshed access token.', {
      expires_in: expiresIn,
      new_expiry: new Date(newExpiry).toISOString(),
    })

    return {
      ...token,
      accessToken: refreshedTokens.access_token,
      accessTokenExpires: newExpiry,
      refreshToken: refreshedTokens.refresh_token ?? token.refreshToken,
      idToken: refreshedTokens.id_token ?? token.idToken,
      error: undefined, // Clear any previous errors
    }
  } catch (error) {
    log('🔴 ERROR refreshing access token.', { error })

    // Return token with error flag - this will trigger re-authentication
    return {
      ...token,
      error: 'RefreshAccessTokenError',
      // Clear tokens to force re-auth
      accessToken: undefined,
      refreshToken: undefined,
    }
  }
}

// Keycloak is hosted on Google Cloud Run
// KEYCLOAK_SERVER_URL must be set to your Cloud Run URL
const keycloakServerUrl = process.env.KEYCLOAK_SERVER_URL
const keycloakRealm = process.env.KEYCLOAK_REALM || 'supervity'

if (!keycloakServerUrl) {
  console.error('❌ KEYCLOAK_SERVER_URL environment variable is not set!')
}

const keycloakIssuer = `${keycloakServerUrl}/realms/${keycloakRealm}`

log(`Configuring Keycloak provider with issuer: ${keycloakIssuer}`)

const authOptions: AuthOptions = {
  providers: [
    KeycloakProvider({
      // Override the name to hide "Keycloak" branding
      name: 'SSO',
      clientId: process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
      issuer: keycloakIssuer,
      wellKnown: `${keycloakIssuer}/.well-known/openid-configuration`,
      authorization: {
        params: {
          // Request offline_access for longer-lived refresh tokens
          scope: 'openid email profile offline_access',
        },
      },
    }),
    // DEV ONLY: empty unless DEV_AUTH_ENABLED=true (see lib/auth/dev-mock.ts)
    ...devMockProviders(),
  ],
  // Custom pages to avoid showing default NextAuth UI with provider names
  pages: {
    signIn: '/auth/signin',
    error: '/auth/error',
  },
  // Session configuration
  session: {
    strategy: 'jwt',
    // Max session age - NextAuth will handle refresh within this window
    maxAge: 24 * 60 * 60, // 24 hours
  },
  callbacks: {
    async jwt({ token, account, user }) {
      log('JWT callback triggered.')

      // DEV ONLY: mock login. The backend token is issued at sign-in, no refresh flow.
      if (account?.provider === DEV_MOCK_PROVIDER_ID && user) {
        return {
          ...token,
          provider: DEV_MOCK_PROVIDER_ID,
          accessToken: user.accessToken,
          accessTokenExpires: Date.now() + 8 * 60 * 60 * 1000,
          error: undefined,
        }
      }
      if (token.provider === DEV_MOCK_PROVIDER_ID) {
        return (token.accessTokenExpires as number) > Date.now()
          ? token
          : { ...token, error: 'RefreshAccessTokenError', accessToken: undefined }
      }

      // Initial sign in
      if (account) {
        log('Initial sign-in flow. Received account object from Keycloak.', {
          provider: account.provider,
          type: account.type,
          expires_at: account.expires_at,
          expires_in: account.expires_in,
        })

        const expiresIn = Number(account.expires_in) || 300
        const accessTokenExpires = Date.now() + expiresIn * 1000

        return {
          ...token,
          accessToken: account.access_token,
          accessTokenExpires,
          refreshToken: account.refresh_token,
          idToken: account.id_token,
          error: undefined,
        }
      }

      // Check if token has an error from previous refresh attempt
      if (token.error === 'RefreshAccessTokenError') {
        log('🔴 Previous refresh failed. User needs to re-authenticate.')
        return token
      }

      // Calculate time until token expires
      const tokenExpiry = token.accessTokenExpires as number
      const timeUntilExpiry = tokenExpiry - Date.now()
      const bufferMs = TOKEN_REFRESH_BUFFER_SECONDS * 1000

      // Return previous token if the access token has not expired yet (with buffer)
      if (timeUntilExpiry > bufferMs) {
        log(
          `Access token still valid. Expires in ${Math.round(timeUntilExpiry / 1000)}s`
        )
        return token
      }

      // Access token has expired or will expire soon, try to refresh
      log(
        `Token expiring soon (${Math.round(timeUntilExpiry / 1000)}s). Refreshing...`
      )
      return refreshAccessToken(token)
    },
    async session({ session, token }) {
      log('Session callback triggered.')

      // Pass token data to session
      session.accessToken = token.accessToken as string
      session.idToken = token.idToken as string
      session.error = token.error as string | undefined
      session.provider = token.provider

      // Include token expiry time for client-side awareness
      session.accessTokenExpires = token.accessTokenExpires as number

      // Decode access token to get roles (both realm and client roles)
      if (token.accessToken) {
        try {
          const tokenPayload = JSON.parse(
            Buffer.from(
              (token.accessToken as string).split('.')[1],
              'base64'
            ).toString()
          )
          // Extract realm roles
          const realmRoles = tokenPayload.realm_access?.roles || []
          
          // Extract client roles for our specific client
          const clientId = process.env.KEYCLOAK_CLIENT_ID || ''
          const clientRoles = tokenPayload.resource_access?.[clientId]?.roles || []
          
          // Combine and deduplicate roles
          const allRoles = [...new Set([...realmRoles, ...clientRoles])]
          session.roles = allRoles
          
          log('Extracted roles from token:', { 
            realmRoles, 
            clientRoles, 
            combinedRoles: allRoles 
          })
        } catch (error) {
          log('Failed to decode access token for roles:', { error })
          session.roles = []
        }
      } else {
        session.roles = []
      }

      log('Returning session object to client.', {
        user: session.user,
        accessToken: session.accessToken ? 'Present' : 'Absent',
        roles: session.roles,
        error: session.error,
        expiresAt: session.accessTokenExpires
          ? new Date(session.accessTokenExpires).toISOString()
          : 'N/A',
      })

      return session
    },
    async redirect({ url, baseUrl }) {
      log(`Redirect callback triggered. url: ${url}, baseUrl: ${baseUrl}`)

      // Handle base path correctly
      const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''

      // Allows relative callback URLs
      if (url.startsWith('/')) {
        // Check if url already starts with basePath to avoid duplication
        if (basePath && url.startsWith(basePath)) {
          return `${baseUrl}${url}`
        }
        return `${baseUrl}${basePath}${url}`
      }
      // Allows callback URLs on the same origin
      else if (new URL(url).origin === baseUrl) return url
      // Default redirect to base path
      return `${baseUrl}${basePath}`
    },
  },
  events: {
    async signIn({ user, account }) {
      log('✅ User signed in successfully.', {
        user: user,
        account: { provider: account?.provider, type: account?.type },
      })
    },
    async signOut() {
      log('User signing out. Invalidating Keycloak session.')
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  debug: process.env.SUPERVITY_AUTH_DEBUG === 'true',
}

const handler = NextAuth(authOptions)
export { handler as GET, handler as POST }
