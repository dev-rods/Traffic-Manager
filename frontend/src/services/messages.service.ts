import { api } from './api'

export interface SendMessagePayload {
  patient_id: string
  phone: string
  template: string
  body: string
}

export interface SendMessageResponse {
  status: string
  messageId?: string
  providerMessageId?: string
}

export const messagesService = {
  send(clinicId: string, payload: SendMessagePayload) {
    return api
      .post<SendMessageResponse>('/send', {
        clinicId,
        phone: payload.phone,
        type: 'text',
        content: payload.body,
        metadata: { patient_id: payload.patient_id, template: payload.template },
      })
      .then((r) => r.data)
  },
}
