import { api } from './api'
import type { PapelDoUsuario } from '@/types'

export interface UsuarioDaClinica {
  id: string
  email: string
  name: string | null
  role: PapelDoUsuario
  active: boolean
  /** Quantos dias à frente enxerga a agenda. `null` = padrão do servidor. */
  agenda_days_ahead: number | null
  /** Data limite, YYYY-MM-DD. `null` = sem limite fixo. */
  agenda_visible_until: string | null
  last_login_at?: string | null
}

export interface AlteracaoDeUsuario {
  agenda_days_ahead?: number | null
  agenda_visible_until?: string | null
  active?: boolean
  name?: string
}

interface ListaDeUsuarios {
  status: string
  users: UsuarioDaClinica[]
  total: number
}

interface RespostaDeAlteracao {
  status: string
  message: string
  user: UsuarioDaClinica
}

export const clinicUsersService = {
  list(clinicId: string) {
    return api
      .get<ListaDeUsuarios>(`/clinics/${clinicId}/users`)
      .then((r) => r.data.users)
  },

  update(clinicId: string, userId: string, dados: AlteracaoDeUsuario) {
    return api
      .patch<RespostaDeAlteracao>(`/clinics/${clinicId}/users/${userId}`, dados)
      .then((r) => r.data)
  },
}
