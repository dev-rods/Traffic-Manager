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

export type DeliveryState = 'delivered' | 'sent_only' | 'pending'

export interface DeliveryStatusItem {
  providerMessageId: string
  delivery: DeliveryState
  lastStatus: string | null
  lastStatusAt: string | null
}

export interface DeliveryStatusResponse {
  status: string
  results: DeliveryStatusItem[]
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

  getDeliveryStatus(
    clinicId: string,
    sends: Array<{ providerMessageId: string; sentAtIso: string }>,
  ) {
    return api
      .post<DeliveryStatusResponse>('/messages/delivery-status', { clinicId, sends })
      .then((r) => r.data)
  },
}
