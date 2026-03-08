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

export type DashboardPeriod = 'today' | 'current_week' | 'current_month'

export interface DashboardData {
  summary: ReportSummary
  today_appointments: DashboardAppointment[]
  top_services: ServiceStat[]
  discount_breakdown: DiscountStat[]
  daily_counts: DailyCount[]
}

export interface DashboardAppointment {
  id: string
  patient_name: string
  patient_phone: string
  service_name: string
  areas: string[]
  professional: string
  scheduled_at: string
  duration_minutes: number
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed'
  original_price_cents: number
  discount_pct: number
  discount_reason: 'first_session' | 'tier_2' | 'tier_3' | null
  final_price_cents: number
}

export const reportsService = {
  get(clinicId: string, period: ReportPeriod) {
    return api
      .get<ReportData>(`/clinics/${clinicId}/reports`, { params: { period } })
      .then((r) => r.data)
  },

  dashboard(clinicId: string) {
    return api
      .get<DashboardData>(`/clinics/${clinicId}/dashboard`)
      .then((r) => r.data)
  },
}
