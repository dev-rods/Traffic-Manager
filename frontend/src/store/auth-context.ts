import { createContext } from 'react'
import type { AuthCredentials, Clinic, PapelDoUsuario, JanelaDaAgenda } from '@/types'

interface AuthState {
  isAuthenticated: boolean
  clinicId: string | null
  clinic: Clinic | null
  isLoading: boolean
  /** ADMIN vê tudo; STAFF vê a agenda e o prontuário. */
  papel: PapelDoUsuario
  /** De quando até quando o STAFF enxerga a agenda. `null` para ADMIN. */
  janela: JanelaDaAgenda | null
  nome: string | null
}

export interface AuthContextValue extends AuthState {
  login: (credentials: AuthCredentials) => Promise<void>
  logout: () => void
  /** Atalho de leitura. Quem decide de verdade continua sendo o servidor. */
  ehAdmin: boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)
