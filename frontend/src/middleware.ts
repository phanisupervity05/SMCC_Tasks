// frontend/src/middleware.ts
import { withAuth } from 'next-auth/middleware'
import { NextResponse } from 'next/server'

const isAuthDebug = process.env.SUPERVITY_AUTH_DEBUG === 'true'

function log(message: string, data?: object) {
  if (isAuthDebug) {
    console.log(
      `[AUTH_DEBUG | Middleware] ${new Date().toISOString()}: ${message}`,
      data || ''
    )
  }
}

// Helper to decode JWT and extract roles
function getRolesFromToken(accessToken: string): string[] {
  try {
    const payload = JSON.parse(
      Buffer.from(accessToken.split('.')[1], 'base64').toString()
    )
    const realmRoles = payload.realm_access?.roles || []
    const clientId = process.env.KEYCLOAK_CLIENT_ID || ''
    const clientRoles = payload.resource_access?.[clientId]?.roles || []
    return [...new Set([...realmRoles, ...clientRoles])]
  } catch {
    return []
  }
}

// Pages that pending users ARE allowed to access
const PENDING_ALLOWED_PATHS = ['/', '/auth', '/api/auth']

export default withAuth(
  function middleware(req) {
    const token = req.nextauth.token
    const pathname = req.nextUrl.pathname
    log(`Running for path: ${pathname}`)

    // Check if token has a refresh error
    if (token?.error === 'RefreshAccessTokenError') {
      log('🔴 Token refresh error detected. Redirecting to sign-in.')
      const signInUrl = new URL('/auth/signin', req.url)
      signInUrl.searchParams.set('callbackUrl', req.url)
      return NextResponse.redirect(signInUrl)
    }

    // Check if user is pending and trying to access restricted pages
    if (token?.accessToken) {
      const roles = getRolesFromToken(token.accessToken as string)
      const isPending = roles.includes('pending') && !roles.includes('user') && !roles.includes('admin')
      
      if (isPending) {
        // Check if trying to access a page other than allowed ones
        const isAllowed = PENDING_ALLOWED_PATHS.some(path => 
          pathname === path || pathname.startsWith(path + '/')
        )
        
        if (!isAllowed) {
          log(`🔒 Pending user trying to access ${pathname}. Redirecting to dashboard.`)
          return NextResponse.redirect(new URL('/', req.url))
        }
      }
    }

    // Token is valid, continue
    return NextResponse.next()
  },
  {
    callbacks: {
      authorized: ({ token, req }) => {
        // If there's no token at all, not authorized
        if (!token) {
          log(
            `No token found for path: ${req.nextUrl.pathname}. Redirecting to sign-in.`
          )
          return false
        }

        // If token has refresh error, we'll handle redirect in middleware function above
        // but still return true here to let middleware run
        if (token.error === 'RefreshAccessTokenError') {
          log(`Token has refresh error for path: ${req.nextUrl.pathname}`)
          return true // Let middleware handle the redirect
        }

        log(
          `Authorization check for path: ${req.nextUrl.pathname}. User is authorized.`
        )
        return true
      },
    },
  }
)

export const config = {
  matcher: [
    // Exclude: api/auth routes, auth pages, static files, and images
    '/((?!api/auth|auth/|_next/static|_next/image|favicon.ico|.*\\.svg|.*\\.png|.*\\.ico).*)',
  ],
}
