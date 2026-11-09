// frontend/types/next-auth.d.ts
import NextAuth from 'next-auth'
import { JWT } from 'next-auth/jwt'

declare module 'next-auth' {
  interface Session {
    accessToken?: string
    idToken?: string
    error?: string
    accessTokenExpires?: number
    roles?: string[]
    sub?: string  // User ID from Keycloak
    provider?: string  // 'dev-mock' for the dev-only mock login
  }

  interface User {
    id?: string
    sub?: string
    accessToken?: string  // dev-mock login only
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    accessToken?: string
    accessTokenExpires?: number
    refreshToken?: string
    error?: string
    idToken?: string
    provider?: string
  }
}
