import { api } from './api'

export interface Professional {
  id: string
  clinic_id: string
  name: string
  role: string | null
  /** Registro no conselho (ex.: CRBM 12345), impresso no termo de consentimento (PRD 036). */
  registro_conselho: string | null
  active: boolean
}

export interface UpdateProfessionalPayload {
  name?: string
  role?: string | null
  registro_conselho?: string | null
  active?: boolean
}

interface ListProfessionalsResponse {
  status: string
  professionals: Professional[]
}

export const professionalsService = {
  list(clinicId: string) {
    return api
      .get<ListProfessionalsResponse>(`/clinics/${clinicId}/professionals`)
      .then((r) => r.data.professionals)
  },

  update(clinicId: string, professionalId: string, payload: UpdateProfessionalPayload) {
    return api
      .put<{ professional: Professional }>(
        `/clinics/${clinicId}/professionals/${professionalId}`,
        payload
      )
      .then((r) => r.data.professional)
  },
}
