import { api } from './api'
import type {
  AvailabilityRule,
  CreateAvailabilityRulePayload,
  AvailabilityException,
  CreateAvailabilityExceptionPayload,
} from '@/types'

interface ListAvailabilityRulesResponse {
  status: string
  data: AvailabilityRule[]
}

interface RuleResponse {
  status: string
  data: AvailabilityRule
}

interface ListExceptionsResponse {
  status: string
  data: AvailabilityException[]
}

interface ExceptionResponse {
  status: string
  data: AvailabilityException
}

interface AvailableSlotsResponse {
  status: string
  clinicId: string
  date: string
  serviceId: string
  slots: string[]
  totalSlots: number
}

export const availabilityService = {
  listRules(clinicId: string) {
    return api
      .get<ListAvailabilityRulesResponse>(`/clinics/${clinicId}/availability-rules`)
      .then((r) => r.data)
  },

  createRule(clinicId: string, payload: CreateAvailabilityRulePayload) {
    return api
      .post<RuleResponse>(`/clinics/${clinicId}/availability-rules`, payload)
      .then((r) => r.data.data)
  },

  deleteRule(ruleId: string) {
    return api.delete(`/availability-rules/${ruleId}`).then((r) => r.data)
  },

  listExceptions(clinicId: string, params?: { from_date?: string; to_date?: string }) {
    return api
      .get<ListExceptionsResponse>(`/clinics/${clinicId}/availability-exceptions`, { params })
      .then((r) => r.data.data)
  },

  createException(clinicId: string, payload: CreateAvailabilityExceptionPayload) {
    return api
      .post<ExceptionResponse>(`/clinics/${clinicId}/availability-exceptions`, payload)
      .then((r) => r.data.data)
  },

  getSlots(clinicId: string, date: string, serviceId: string, totalDuration?: number) {
    return api
      .get<AvailableSlotsResponse>(`/clinics/${clinicId}/available-slots`, {
        params: { date, serviceId, ...(totalDuration ? { totalDuration } : {}) },
      })
      .then((r) => r.data)
  },
}
