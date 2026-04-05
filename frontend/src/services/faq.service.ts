import { api } from './api'
import type { FaqItem, CreateFaqPayload } from '@/types'

interface ListFaqResponse {
  status: string
  data: FaqItem[]
}

interface FaqResponse {
  status: string
  data: FaqItem
}

export const faqService = {
  list(clinicId: string) {
    return api
      .get<ListFaqResponse>(`/clinics/${clinicId}/faq`)
      .then((r) => r.data.data)
  },

  create(clinicId: string, payload: CreateFaqPayload) {
    return api
      .post<FaqResponse>(`/clinics/${clinicId}/faq`, payload)
      .then((r) => r.data.data)
  },

  update(faqId: string, payload: Partial<CreateFaqPayload> & { active?: boolean }) {
    return api
      .put<FaqResponse>(`/faq/${faqId}`, payload)
      .then((r) => r.data.data)
  },
}
