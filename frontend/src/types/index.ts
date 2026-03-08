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
export type AppointmentStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed'

export interface Appointment {
  id: string
  clinic_id: string
  patient_id: string
  patient?: Patient
  service_id: string
  service?: Service
  areas?: Area[]
  professional: string
  scheduled_at: string
  duration_minutes: number
  status: AppointmentStatus
  discount_pct: number
  discount_reason: DiscountReason
  original_price_cents: number
  final_price_cents: number
  full_name: string
}

export interface CreateAppointmentPayload {
  patient_id: string
  service_id: string
  area_ids: string[]
  professional: string
  scheduled_at: string
}

export interface UpdateAppointmentPayload {
  service_id?: string
  area_ids?: string[]
  professional?: string
  scheduled_at?: string
  status?: AppointmentStatus
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
