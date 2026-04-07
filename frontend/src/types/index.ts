// ── Clinic ────────────────────────────────────────────────────
export interface Clinic {
  clinic_id: string
  name: string
  owner_email: string
  phone: string | null
  address: string | null
  timezone: string | null
  buffer_minutes: number | null
  max_future_dates: number | null
  max_session_minutes: number | null
  display_name: string | null
  welcome_message: string | null
  welcome_intro_message: string | null
  pre_session_instructions: string | null
  zapi_instance_id: string | null
  zapi_instance_token: string | null
  use_agent: boolean
  bot_paused: boolean
  batch_message_template: string | null
  active: boolean
}

export interface UpdateClinicPayload {
  name?: string
  display_name?: string
  phone?: string
  address?: string
  buffer_minutes?: number
  max_future_dates?: number
  max_session_minutes?: number
  welcome_message?: string
  welcome_intro_message?: string
  pre_session_instructions?: string
  zapi_instance_id?: string
  zapi_instance_token?: string
  use_agent?: boolean
  bot_paused?: boolean
  batch_message_template?: string
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
  gender?: 'M' | 'F'
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

export type DiscountReason = 'first_session' | 'tier_2' | 'tier_3' | 'partnership' | 'custom' | null

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
  discountPct?: number
  discountReason?: string
}

export interface UpdateAppointmentPayload {
  status?: AppointmentStatus
  notes?: string
  date?: string
  time?: string
  serviceId?: string
  serviceAreaPairs?: { serviceId: string; areaId: string }[]
  discountPct?: number
  discountReason?: string | null
}

// ── Availability Rule ────────────────────────────────────────
export interface AvailabilityRule {
  id: string
  clinic_id: string
  day_of_week: number | null  // 0=Sun, 6=Sat
  rule_date: string | null    // YYYY-MM-DD
  start_time: string          // HH:MM:SS
  end_time: string            // HH:MM:SS
  professional_id: string | null
  active: boolean
}

export interface CreateAvailabilityRulePayload {
  day_of_week?: number
  rule_date?: string
  start_time: string
  end_time: string
}

export interface AvailabilityException {
  id: string
  clinic_id: string
  exception_date: string
  exception_type: 'BLOCKED' | 'SPECIAL_HOURS'
  start_time: string | null
  end_time: string | null
  reason: string | null
  active: boolean
}

export interface CreateAvailabilityExceptionPayload {
  exception_date: string
  exception_type: 'BLOCKED' | 'SPECIAL_HOURS'
  start_time?: string
  end_time?: string
  reason?: string
}

// ── Clinic Area (global catalog) ─────────────────────────────
export interface ClinicArea {
  id: string
  clinic_id: string
  name: string
  display_order: number
  active: boolean
}

export interface CreateAreaPayload {
  name: string
  display_order?: number
}

// ── FAQ ──────────────────────────────────────────────────────
export interface FaqItem {
  id: string
  clinic_id: string
  question_key: string
  question_label: string
  answer: string
  display_order: number
  active: boolean
}

export interface CreateFaqPayload {
  question_key: string
  question_label: string
  answer: string
  display_order?: number
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

// ── Bot / Conversations ──────────────────────────────────────
export interface ActiveConversation {
  phone: string
  state: string
  bot_paused: boolean
  attendant_active_until: number | null
  updated_at: string
}

export interface ConversationPreview {
  phone: string
  last_message: string
  last_direction: 'INBOUND' | 'OUTBOUND'
  last_message_at: string
  sender_name: string
}

export interface ConversationMessage {
  id: string
  direction: 'INBOUND' | 'OUTBOUND'
  content: string
  message_type: string
  status: string
  created_at: string
  sender_name: string
}

export interface BotMetrics {
  total_conversations: number
  messages_sent: number
  conversion_rate: number
  total_leads: number
  booked_leads: number
  handoff_count: number
  daily_conversations: Record<string, number>
}

// ── Lead ─────────────────────────────────────────────────────
export interface Lead {
  id: string
  clinic_id: string
  phone: string
  name: string | null
  booked: boolean
  source: string
  first_appointment_id: string | null
  first_appointment_value: number | null
  raw_message: string | null
  created_at: string
  updated_at: string
}
