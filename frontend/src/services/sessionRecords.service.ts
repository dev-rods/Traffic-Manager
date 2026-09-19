import { api } from './api'
import type {
  ListaDeRegistros,
  ProtocoloLaser,
  RegistroDeSessao,
  RegistroPayload,
  TrilhaDeEdicoes,
} from '@/types'

export const sessionRecordsService = {
  list(clinicId: string, patientId: string) {
    return api
      .get<ListaDeRegistros>(`/clinics/${clinicId}/patients/${patientId}/session-records`)
      .then((r) => r.data)
  },

  create(clinicId: string, patientId: string, payload: RegistroPayload) {
    return api
      .post<{ record: RegistroDeSessao }>(
        `/clinics/${clinicId}/patients/${patientId}/session-records`,
        payload,
      )
      .then((r) => r.data.record)
  },

  update(clinicId: string, recordId: string, payload: RegistroPayload) {
    return api
      .put<{ record: RegistroDeSessao }>(
        `/clinics/${clinicId}/session-records/${recordId}`,
        payload,
      )
      .then((r) => r.data.record)
  },

  remove(clinicId: string, recordId: string) {
    return api
      .delete(`/clinics/${clinicId}/session-records/${recordId}`)
      .then((r) => r.data)
  },

  history(clinicId: string, recordId: string) {
    return api
      .get<TrilhaDeEdicoes>(`/clinics/${clinicId}/session-records/${recordId}/history`)
      .then((r) => r.data)
  },

  protocol(clinicId: string) {
    return api
      .get<ProtocoloLaser>(`/clinics/${clinicId}/laser-protocol`)
      .then((r) => r.data)
  },
}
