import { api } from './api'

export interface Professional {
  id: string
  clinic_id: string
  name: string
  role: string | null
  active: boolean
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
}
