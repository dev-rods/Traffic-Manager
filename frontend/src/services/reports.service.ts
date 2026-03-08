import { api } from './api'

export type ReportPeriod = 'current_month' | 'last_3_months' | 'current_year'

export interface ReportSummary {
  total_appointments: number
  confirmed_appointments: number
  cancelled_appointments: number
  new_patients: number
  gross_revenue_cents: number
  total_discount_cents: number
  net_revenue_cents: number
  confirmation_rate: number     // 0–100
  cancellation_rate: number     // 0–100
}

export interface ServiceStat {
  service_id: string
  service_name: string
  count: number
  revenue_cents: number
}

export interface DiscountStat {
  reason: 'first_session' | 'tier_2' | 'tier_3'
  count: number
  total_discount_cents: number
}

export interface DailyCount {
  date: string   // YYYY-MM-DD
  count: number
}

export interface ReportData {
  period: ReportPeriod
  summary: ReportSummary
  top_services: ServiceStat[]
  discount_breakdown: DiscountStat[]
  daily_counts: DailyCount[]
}

export const reportsService = {
  get(clinicId: string, period: ReportPeriod) {
    return api
      .get<ReportData>(`/clinics/${clinicId}/reports`, { params: { period } })
      .then((r) => r.data)
  },
}
