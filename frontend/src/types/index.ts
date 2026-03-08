// ── Clinic ────────────────────────────────────────────────────
export interface Clinic {
  clinic_id: string
  name: string
  owner_email: string
}

// ── Patient ───────────────────────────────────────────────────
export interface Patient {
  id: string
  clinic_id: string
  phone: string
  name: string
  gender: 'M' | 'F'
  created_at: string
  updated_at: string
}

export interface CreatePatientPayload {
  name: string
  phone: string
  gender: 'M' | 'F'
}

export interface PatientWithStats extends Patient {
  total_visits: number
  last_visit: string | null
  next_visit: string | null
  total_spent_cents: number
}

// ── Service & Area ────────────────────────────────────────────
export interface Area {
  id: string
  name: string
  service_id: string
  price_cents: number
  duration_minutes: number
}

export interface Service {
  id: string
  name: string
  clinic_id: string
  price_cents: number
  areas?: Area[]
}

// ── Discount ──────────────────────────────────────────────────
export interface DiscountRule {
  clinic_id: string
  first_session_discount_pct: number
  tier_2_min_areas: number
  tier_2_max_areas: number
  tier_2_discount_pct: number
  tier_3_min_areas: number
  tier_3_discount_pct: number
  is_active: boolean
}

export type DiscountReason = 'first_session' | 'tier_2' | 'tier_3' | null

export interface DiscountBreakdown {
  original_price_cents: number
  discount_pct: number
  discount_reason: DiscountReason
  final_price_cents: number
}

// ── Appointment ───────────────────────────────────────────────
export type AppointmentStatus = 'CONFIRMED' | 'CANCELLED'

export interface Appointment {
  id: string
  clinic_id: string
  service_id: string
  appointment_date: string   // YYYY-MM-DD
  start_time: string         // HH:MM:SS
  end_time: string           // HH:MM:SS
  status: AppointmentStatus
  notes: string | null
  patient_name: string | null
  patient_phone: string | null
  service_name: string | null
  professional_name: string | null
  areas: string | null       // comma-separated area names
  area_ids: string | null    // comma-separated area UUIDs
  duration_minutes: number | null
  discount_pct: number
  discount_reason: DiscountReason
  original_price_cents: number | null
  final_price_cents: number | null
  full_name: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface ListAppointmentsResponse {
  status: string
  clinicId: string
  appointments: Appointment[]
  total: number
}

export interface CreateAppointmentPayload {
  clinicId: string
  phone: string
  serviceId: string
  date: string
  time: string
  serviceAreaPairs?: { serviceId: string; areaId: string }[]
  professionalId?: string
  fullName?: string
}

export interface UpdateAppointmentPayload {
  status?: AppointmentStatus
  notes?: string
  date?: string
  time?: string
  serviceId?: string
  serviceAreaPairs?: { serviceId: string; areaId: string }[]
}

// ── Auth ──────────────────────────────────────────────────────
export interface AuthCredentials {
  email: string
  password: string
}

export interface AuthResponse {
  token: string
  clinic_id: string
  clinic: Clinic
}

// ── API responses ─────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
}

export interface ApiError {
  message: string
  code?: string
}
