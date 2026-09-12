export interface Clinic {
  clinic_id: string
  name: string
  display_name: string | null
  logo_url: string | null
  favicon_url: string | null
  timezone: string
}

export interface Service {
  id: string
  name: string
  duration_minutes: number
  price_cents: number | null
  description: string | null
}

export interface Professional {
  id: string
  name: string
  role: string | null
  photo_url: string | null
}

export interface BootstrapResponse {
  status: 'SUCCESS'
  clinic: Clinic
  services: Service[]
  professionals: Professional[]
}

export interface Appointment {
  id: string
  clinic_id: string
  patient_id: string
  professional_id: string | null
  service_id: string
  service_name?: string
  appointment_date: string
  start_time: string
  end_time: string
  total_duration_minutes: number | null
  final_price_cents: number | null
  original_price_cents: number | null
  full_name: string | null
  status: string
}

export interface CreateAppointmentPayload {
  token: string
  phone: string
  fullName: string
  serviceIds: string[]
  date: string
  time: string
  professionalId?: string
}

export type WizardStep = 'cart' | 'professional' | 'schedule' | 'customer' | 'success'
