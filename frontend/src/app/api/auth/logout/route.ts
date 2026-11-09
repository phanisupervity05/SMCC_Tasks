// frontend/src/app/api/auth/logout/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { getToken } from 'next-auth/jwt'

const isAuthDebug = process.env.SUPERVITY_AUTH_DEBUG === 'true'

function log(message: string, data?: object) {
  if (isAuthDebug) {
    const logData = data ? JSON.stringify(data, null, 2) : ''
    console.log(
      `[AUTH_DEBUG | Logout] ${new Date().toISOString()}: ${message}\n${logData}`
    )
  }
}

export async function GET(request: NextRequest) {
  try {
    log('🚪 Custom logout endpoint called.')

    // Get the token from the JWT (this contains the idToken)
    const token = await getToken({
      req: request,
      secret: process.env.NEXTAUTH_SECRET,
    })

    const idToken = token?.idToken

    // DEV ONLY: a mock session has no Keycloak session, just clear the cookies.
    if (token?.provider === 'dev-mock') {
      const base = process.env.NEXT_PUBLIC_BASE_PATH || ''
      return NextResponse.redirect(`${request.nextUrl.origin}${base}/auth/clear-session`)
    }

    log('Token retrieved:', {
      hasToken: !!token,
      hasIdToken: !!idToken,
    })

    // Environment configuration
    const keycloakPublicUrl =
      process.env.NEXT_PUBLIC_KEYCLOAK_URL || 'http://localhost:8080'
    const keycloakRealm = process.env.KEYCLOAK_REALM || 'supervity'
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
    const appBaseUrl =
      process.env.NEXTAUTH_URL?.replace('/api/auth', '') ||
      `http://localhost:3001${basePath}`

    log('Logout configuration:', {
      keycloakPublicUrl,
      keycloakRealm,
      appBaseUrl,
      hasIdToken: !!idToken,
      hasToken: !!token,
    })

    // Construct the Keycloak end_session_endpoint URL
    const keycloakLogoutUrl = new URL(
      `${keycloakPublicUrl}/realms/${keycloakRealm}/protocol/openid-connect/logout`
    )

    // After Keycloak logs out, redirect to NextAuth signout to clear the session cookie
    // Then NextAuth will redirect back to the home page
    const nextAuthSignoutUrl = `${appBaseUrl}/api/auth/signout?callbackUrl=${encodeURIComponent(appBaseUrl)}`
    keycloakLogoutUrl.searchParams.set(
      'post_logout_redirect_uri',
      nextAuthSignoutUrl
    )

    // Add id_token_hint if available (helps Keycloak identify the session to end)
    if (idToken) {
      keycloakLogoutUrl.searchParams.set('id_token_hint', idToken)
      log('✅ Including id_token_hint in logout request.')
    } else {
      log(
        '⚠️  No id_token available in session. Logout may still work but could be less reliable.'
      )
    }

    log('Redirecting to Keycloak logout URL:', {
      url: keycloakLogoutUrl.toString(),
    })

    // Redirect to Keycloak logout
    // Keycloak will end the session and redirect back to post_logout_redirect_uri
    return NextResponse.redirect(keycloakLogoutUrl.toString())
  } catch (error) {
    log('🔴 ERROR during logout:', { error })

    // Fallback: redirect to home page
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''
    const appBaseUrl = `http://localhost:3001${basePath}`
    return NextResponse.redirect(appBaseUrl)
  }
}
