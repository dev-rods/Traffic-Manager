import { createContext, useCallback, useMemo, useState } from 'react'
import type { AuthCredentials, Clinic } from '@/types'
import { api } from '@/services/api'

// ── Types ─────────────────────────────────────────────────────
interface AuthState {
  isAuthenticated: boolean
  clinicId: string | null
  clinic: Clinic | null
  isLoading: boolean
}

export interface AuthContextValue extends AuthState {
  login: (credentials: AuthCredentials) => Promise<void>
  logout: () => void
}

// ── Context ───────────────────────────────────────────────────
export const AuthContext = createContext<AuthContextValue | null>(null)

const TOKEN_KEY = 'tm_token'
const CLINIC_ID_KEY = 'tm_clinic_id'

function getInitialState(): AuthState {
  const token = localStorage.getItem(TOKEN_KEY)
  const clinicId = localStorage.getItem(CLINIC_ID_KEY)
  if (token && clinicId) {
    return { isAuthenticated: true, clinicId, clinic: null, isLoading: false }
  }
  return { isAuthenticated: false, clinicId: null, clinic: null, isLoading: false }
}

// ── Provider ──────────────────────────────────────────────────
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(getInitialState)

  const login = useCallback(async ({ email, password }: AuthCredentials) => {
    const response = await api.post<{ token: string; clinic_id: string; clinic: Clinic }>(
      '/auth/login',
      { email, password }
    )

    const { token, clinic_id, clinic } = response.data

    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(CLINIC_ID_KEY, clinic_id)

    setState({ isAuthenticated: true, clinicId: clinic_id, clinic, isLoading: false })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(CLINIC_ID_KEY)
    setState({ isAuthenticated: false, clinicId: null, clinic: null, isLoading: false })
  }, [])

  const value = useMemo(() => ({ ...state, login, logout }), [state, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
