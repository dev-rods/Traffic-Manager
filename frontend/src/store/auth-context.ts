import { createContext } from 'react'
import type { AuthCredentials, Clinic } from '@/types'

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

export const AuthContext = createContext<AuthContextValue | null>(null)
