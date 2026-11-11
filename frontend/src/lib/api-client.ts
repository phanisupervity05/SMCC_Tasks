import { getSession, signIn } from 'next-auth/react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || ''

export interface ApiFieldError {
  field: string
  message: string
}

/** Thrown for non-2xx responses. `fieldErrors` is set when the backend names the fields at fault. */
export class ApiError extends Error {
  status: number
  fieldErrors?: ApiFieldError[]
  constructor(message: string, status: number, fieldErrors?: ApiFieldError[]) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

/**
 * A robust API client that handles authentication and base path resolution.
 * @param endpoint The API endpoint to call, e.g., '/api/test' or '/api/admin/dashboard'.
 *                 The endpoint should include the '/api' prefix.
 * @param options Standard fetch options (method, body, etc.).
 */
async function apiClientFetch<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const session = await getSession()

  const headers = new Headers(options.headers || {})

  if (session?.accessToken) {
    headers.set('Authorization', `Bearer ${session.accessToken}`)
  }

  // Handle session errors that occurred during a token refresh attempt.
  if (session?.error === 'RefreshAccessTokenError') {
    // Force sign-in to get a new, valid session.
    await signIn()
    // Throw an error to stop the current, failing API call.
    throw new Error('Session expired. Please sign in again.')
  }

  // Construct the full URL: http://localhost:8001/app1/api/test
  const fullUrl = `${API_URL}${BASE_PATH}${endpoint}`

  const response = await fetch(fullUrl, { ...options, headers })

  // If the backend returns a 401, it means the token is invalid or expired.
  // This can happen if the backend is restarted or the user's session is revoked.
  // We trigger a re-login to fix the session.
  if (response.status === 401) {
    await signIn()
    throw new Error('Your session has expired. Please sign in again.')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({
      detail: response.statusText,
    }))
    const detail = errorData.detail
    // The calls API returns { error, errors: [{ field, message }] } for rule violations.
    const fieldErrors: ApiFieldError[] | undefined = Array.isArray(detail?.errors)
      ? detail.errors
      : undefined
    const message =
      typeof detail === 'string'
        ? detail
        : fieldErrors?.map((e) => `${e.field}: ${e.message}`).join('; ') ||
          'An API error occurred.'
    throw new ApiError(message, response.status, fieldErrors)
  }

  // Handle responses with no content
  if (response.status === 204) {
    return null as T
  }

  return response.json() as Promise<T>
}

/** Download a file from the API (for example a CSV) with the user's login. Returns the bytes and the file name. */
export async function apiClientDownload(endpoint: string): Promise<{ blob: Blob; filename: string }> {
  const session = await getSession()
  const headers = new Headers()
  if (session?.accessToken) headers.set('Authorization', `Bearer ${session.accessToken}`)
  const response = await fetch(`${API_URL}${BASE_PATH}${endpoint}`, { headers })
  if (response.status === 401) {
    await signIn()
    throw new Error('Your session has expired. Please sign in again.')
  }
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof err.detail === 'string' ? err.detail : 'Download failed.')
  }
  const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')
  return { blob: await response.blob(), filename: match?.[1] ?? 'download.csv' }
}

/**
 * API client with convenience methods for common HTTP operations.
 */
export const apiClient = {
  /**
   * Perform a GET request.
   */
  get: <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, { ...options, method: 'GET' })
  },

  /**
   * Perform a POST request.
   */
  post: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a PUT request.
   */
  put: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a PATCH request.
   */
  patch: <T = unknown>(endpoint: string, data?: unknown, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, {
      ...options,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: data ? JSON.stringify(data) : undefined,
    })
  },

  /**
   * Perform a DELETE request.
   */
  delete: <T = unknown>(endpoint: string, options?: RequestInit): Promise<T> => {
    return apiClientFetch<T>(endpoint, { ...options, method: 'DELETE' })
  },
}

// Default export for backward compatibility
export default apiClientFetch
