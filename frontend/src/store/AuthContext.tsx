import { useCallback, useMemo, useState } from 'react'
import type {
  AuthCredentials,
  Clinic,
  JanelaDaAgenda,
  PapelDoUsuario,
} from '@/types'
import { api } from '@/services/api'
import { AuthContext } from './auth-context'
export type { AuthContextValue } from './auth-context'

interface AuthState {
  isAuthenticated: boolean
  clinicId: string | null
  clinic: Clinic | null
  isLoading: boolean
  papel: PapelDoUsuario
  janela: JanelaDaAgenda | null
  nome: string | null
}

const TOKEN_KEY = 'tm_token'
const CLINIC_ID_KEY = 'tm_clinic_id'
const PAPEL_KEY = 'tm_papel'
const JANELA_KEY = 'tm_janela'
const NOME_KEY = 'tm_nome'

interface RespostaDeLogin {
  token: string
  clinic_id: string
  clinic: Clinic
  role?: PapelDoUsuario
  agenda_window?: JanelaDaAgenda | null
  user?: { id: string; name: string | null; email: string }
}

function leJanela(): JanelaDaAgenda | null {
  const cru = localStorage.getItem(JANELA_KEY)
  if (!cru) return null
  try {
    return JSON.parse(cru) as JanelaDaAgenda
  } catch {
    // Storage corrompido não pode derrubar o app na inicialização.
    return null
  }
}

function getInitialState(): AuthState {
  const token = localStorage.getItem(TOKEN_KEY)
  const clinicId = localStorage.getItem(CLINIC_ID_KEY)
  if (token && clinicId) {
    return {
      isAuthenticated: true,
      clinicId,
      clinic: null,
      isLoading: false,
      // Ausente significa sessão antiga, de antes dos papéis: era admin.
      papel: (localStorage.getItem(PAPEL_KEY) as PapelDoUsuario) ?? 'ADMIN',
      janela: leJanela(),
      nome: localStorage.getItem(NOME_KEY),
    }
  }
  return {
    isAuthenticated: false,
    clinicId: null,
    clinic: null,
    isLoading: false,
    papel: 'ADMIN',
    janela: null,
    nome: null,
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(getInitialState)

  const login = useCallback(async ({ email, password }: AuthCredentials) => {
    const response = await api.post<RespostaDeLogin>('/auth/login', { email, password })

    const { token, clinic_id, clinic, role, agenda_window, user } = response.data
    const papel: PapelDoUsuario = role ?? 'ADMIN'
    const janela = agenda_window ?? null
    const nome = user?.name ?? null

    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(CLINIC_ID_KEY, clinic_id)
    localStorage.setItem(PAPEL_KEY, papel)
    if (janela) localStorage.setItem(JANELA_KEY, JSON.stringify(janela))
    else localStorage.removeItem(JANELA_KEY)
    if (nome) localStorage.setItem(NOME_KEY, nome)
    else localStorage.removeItem(NOME_KEY)

    setState({
      isAuthenticated: true,
      clinicId: clinic_id,
      clinic,
      isLoading: false,
      papel,
      janela,
      nome,
    })
  }, [])

  const logout = useCallback(() => {
    for (const chave of [TOKEN_KEY, CLINIC_ID_KEY, PAPEL_KEY, JANELA_KEY, NOME_KEY]) {
      localStorage.removeItem(chave)
    }
    setState({
      isAuthenticated: false,
      clinicId: null,
      clinic: null,
      isLoading: false,
      papel: 'ADMIN',
      janela: null,
      nome: null,
    })
  }, [])

  const value = useMemo(
    () => ({ ...state, login, logout, ehAdmin: state.papel === 'ADMIN' }),
    [state, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
