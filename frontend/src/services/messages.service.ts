import { api } from './api'

export type MessageTemplate = 'confirmacao' | 'lembrete' | 'reagendamento' | 'livre'

export interface SendMessagePayload {
  patient_id: string
  phone: string
  template: MessageTemplate
  body: string             // message text (may be edited by user)
  appointment_id?: string  // optional context
}

export interface SendMessageResponse {
  message_id: string
  status: 'sent' | 'queued' | 'failed'
}

export const messagesService = {
  send(clinicId: string, payload: SendMessagePayload) {
    return api
      .post<SendMessageResponse>(`/clinics/${clinicId}/messages`, payload)
      .then((r) => r.data)
  },
}
