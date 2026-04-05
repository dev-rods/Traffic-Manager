import { api } from './api'
import type { ActiveConversation, ConversationPreview, ConversationMessage, BotMetrics } from '@/types'

interface ActiveConversationsResponse {
  status: string
  conversations: ActiveConversation[]
  total: number
}

interface ConversationsResponse {
  status: string
  conversations: ConversationPreview[]
  total: number
}

interface MessagesResponse {
  status: string
  messages: ConversationMessage[]
  total: number
}

interface BotMetricsResponse {
  status: string
  metrics: BotMetrics
  period: string
}

interface AttendantResponse {
  status: string
  message: string
}

interface AttendantStatusResponse {
  status: string
  bot_paused: boolean
  conversation_state: string
  attendant_active_until: number | null
  ttl_remaining_seconds: number
}

export const botService = {
  // Conversations
  listActive(clinicId: string) {
    return api
      .get<ActiveConversationsResponse>(`/clinics/${clinicId}/conversations/active`)
      .then((r) => r.data)
  },

  listRecent(clinicId: string, limit = 20) {
    return api
      .get<ConversationsResponse>(`/clinics/${clinicId}/conversations`, { params: { limit } })
      .then((r) => r.data)
  },

  getMessages(clinicId: string, phone: string, limit = 50) {
    return api
      .get<MessagesResponse>(`/clinics/${clinicId}/conversations/${phone}/messages`, { params: { limit } })
      .then((r) => r.data)
  },

  // Metrics
  getMetrics(clinicId: string, period: 'today' | 'week' | 'month' = 'today') {
    return api
      .get<BotMetricsResponse>(`/clinics/${clinicId}/bot-metrics`, { params: { period } })
      .then((r) => r.data.metrics)
  },

  // Attendant (pause/resume per phone)
  pauseForPhone(clinicId: string, phone: string) {
    return api
      .post<AttendantResponse>('/attendant/activate', { clinic_id: clinicId, phone })
      .then((r) => r.data)
  },

  resumeForPhone(clinicId: string, phone: string) {
    return api
      .post<AttendantResponse>('/attendant/deactivate', { clinic_id: clinicId, phone })
      .then((r) => r.data)
  },

  getPhoneStatus(clinicId: string, phone: string) {
    return api
      .get<AttendantStatusResponse>('/attendant/status', { params: { clinic_id: clinicId, phone } })
      .then((r) => r.data)
  },
}
