import { createContext, useContext, useEffect, useMemo, useState } from 'react'

interface AuthUser {
  userId: string
  tenantId: string
  roles: string[]
  name: string
}

interface AuthContextValue {
  authenticated: boolean
  loading: boolean
  token: string | null
  user: AuthUser | null
  roles: string[]
  canWrite: boolean
  login: () => Promise<void>
  logout: () => void
  getAccessToken: () => string | null
}

const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL ?? ''
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM ?? 'nxr'
const KEYCLOAK_CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? 'nexora-ui'
const DEV_AUTH_ENABLED = (import.meta.env.VITE_DEV_AUTH_ENABLED ?? 'true') !== 'false'
const STORAGE_KEY = 'nexora.auth'
const VERIFIER_KEY = 'nexora.pkce.verifier'

const AuthContext = createContext<AuthContextValue | null>(null)

function b64url(bytes: ArrayBuffer | Uint8Array) {
  const array = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)
  let binary = ''
  array.forEach(b => { binary += String.fromCharCode(b) })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

async function sha256(value: string) {
  return crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
}

function randomVerifier() {
  const bytes = new Uint8Array(48)
  crypto.getRandomValues(bytes)
  return b64url(bytes)
}

function decodeJwt(token: string): Record<string, unknown> {
  const payload = token.split('.')[1] ?? ''
  const padded = payload.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - payload.length % 4) % 4)
  return JSON.parse(atob(padded))
}

function authBase() {
  return `${KEYCLOAK_URL.replace(/\/$/, '')}/realms/${KEYCLOAK_REALM}/protocol/openid-connect`
}

function isConfigured() {
  return Boolean(KEYCLOAK_URL && KEYCLOAK_REALM && KEYCLOAK_CLIENT_ID)
}

function isDevAuthConfigured() {
  return !isConfigured() && DEV_AUTH_ENABLED
}

function tokenMatchesConfiguredIssuer(token: string) {
  if (!isConfigured()) return true
  try {
    const claims = decodeJwt(token)
    return claims.iss === `${KEYCLOAK_URL.replace(/\/$/, '')}/realms/${KEYCLOAK_REALM}`
  } catch {
    return false
  }
}

function devJwt() {
  const now = Math.floor(Date.now() / 1000)
  const header = b64url(new TextEncoder().encode(JSON.stringify({ alg: 'none', typ: 'JWT' })))
  const payload = b64url(new TextEncoder().encode(JSON.stringify({
    sub: 'dev-admin',
    preferred_username: 'admin',
    name: 'Development Admin',
    groups: ['/tenant-dev'],
    realm_access: { roles: ['platform-admin', 'tenant-admin', 'operator'] },
    iat: now,
    exp: now + 86400,
  })))
  return `${header}.${payload}.`
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState<string | null>(null)
  const [refreshToken, setRefreshToken] = useState<string | null>(null)

  function persist(nextToken: string, nextRefresh: string | null) {
    setToken(nextToken)
    setRefreshToken(nextRefresh)
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: nextToken, refreshToken: nextRefresh }))
  }

  async function exchangeCode(code: string) {
    const verifier = sessionStorage.getItem(VERIFIER_KEY)
    if (!verifier) throw new Error('Missing PKCE verifier')
    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: KEYCLOAK_CLIENT_ID,
      code,
      redirect_uri: window.location.origin + window.location.pathname,
      code_verifier: verifier,
    })
    const response = await fetch(`${authBase()}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
    if (!response.ok) throw new Error('Token exchange failed')
    const data = await response.json()
    persist(data.access_token, data.refresh_token ?? null)
    sessionStorage.removeItem(VERIFIER_KEY)
  }

  async function refreshAccessToken(currentRefreshToken: string) {
    const body = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: KEYCLOAK_CLIENT_ID,
      refresh_token: currentRefreshToken,
    })
    const response = await fetch(`${authBase()}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
    if (!response.ok) throw new Error('Token refresh failed')
    const data = await response.json()
    persist(data.access_token, data.refresh_token ?? currentRefreshToken)
  }

  async function login() {
    if (isDevAuthConfigured()) {
      persist(devJwt(), null)
      window.location.assign('/dashboard')
      return
    }
    if (!isConfigured()) return
    const verifier = randomVerifier()
    const challenge = b64url(await sha256(verifier))
    sessionStorage.setItem(VERIFIER_KEY, verifier)
    const params = new URLSearchParams({
      client_id: KEYCLOAK_CLIENT_ID,
      response_type: 'code',
      redirect_uri: window.location.origin + window.location.pathname,
      scope: 'openid profile email',
      code_challenge: challenge,
      code_challenge_method: 'S256',
    })
    window.location.assign(`${authBase()}/auth?${params}`)
  }

  function logout() {
    const idToken = token
    localStorage.removeItem(STORAGE_KEY)
    setToken(null)
    setRefreshToken(null)
    if (isConfigured()) {
      const params = new URLSearchParams({
        client_id: KEYCLOAK_CLIENT_ID,
        post_logout_redirect_uri: window.location.origin,
      })
      if (idToken) params.set('id_token_hint', idToken)
      window.location.assign(`${authBase()}/logout?${params}`)
    }
  }

  useEffect(() => {
    async function init() {
      try {
        const url = new URL(window.location.href)
        const code = url.searchParams.get('code')
        if (code && isConfigured()) {
          await exchangeCode(code)
          url.searchParams.delete('code')
          url.searchParams.delete('session_state')
          url.searchParams.delete('iss')
          window.history.replaceState({}, document.title, url.toString())
          return
        }
        const saved = localStorage.getItem(STORAGE_KEY)
        if (saved) {
          const parsed = JSON.parse(saved)
          const savedToken = parsed.token ?? null
          if (savedToken && tokenMatchesConfiguredIssuer(savedToken)) {
            setToken(savedToken)
            setRefreshToken(parsed.refreshToken ?? null)
          } else {
            localStorage.removeItem(STORAGE_KEY)
          }
        }
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  useEffect(() => {
    if (!refreshToken) return
    const id = window.setInterval(() => {
      refreshAccessToken(refreshToken).catch(() => logout())
    }, 240000)
    return () => window.clearInterval(id)
  }, [refreshToken])

  const user = useMemo<AuthUser | null>(() => {
    if (!token) return null
    try {
      const claims = decodeJwt(token)
      const groups = (claims.groups as string[] | undefined) ?? []
      const realmAccess = claims.realm_access as { roles?: string[] } | undefined
      const roles = realmAccess?.roles ?? []
      return {
        userId: String(claims.sub ?? ''),
        tenantId: (groups[0] ?? 'global').replace(/^\//, ''),
        roles,
        name: String(claims.preferred_username ?? claims.name ?? claims.sub ?? 'user'),
      }
    } catch {
      return null
    }
  }, [token])

  const roles = user?.roles ?? []
  const canWrite = !isConfigured() || roles.some(r => ['platform-admin', 'tenant-admin', 'operator'].includes(r))
  const value = { authenticated: Boolean(token), loading, token, user, roles, canWrite, login, logout, getAccessToken: () => token }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
