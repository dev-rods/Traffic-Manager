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

// Área de tratamento vinculada a um serviço — duração/preço podem sobrescrever
// os valores base do serviço (mesma junção usada pelo bot de WhatsApp).
export interface ServiceArea {
  service_area_id: string
  service_id: string
  area_id: string
  area_name: string
  display_order: number
  duration_minutes: number
  price_cents: number | null
}

export interface BootstrapResponse {
  status: 'SUCCESS'
  clinic: Clinic
  services: Service[]
  professionals: Professional[]
  serviceAreas: ServiceArea[]
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
  phone: string
  fullName: string
  serviceIds: string[]
  date: string
  time: string
  professionalId?: string
  serviceAreaPairs?: { serviceId: string; areaId: string }[]
}

// Status de um dia no seletor de semana — mesma lógica da AvailabilityEngine
// usada pelo bot: CLOSED (sem regra de agenda), FULL (regra existe, sem vaga),
// AVAILABLE (tem horário livre).
export type DayAvailabilityStatus = 'CLOSED' | 'FULL' | 'AVAILABLE'

export interface DayAvailability {
  status: DayAvailabilityStatus
  slots: string[]
}

// Item do carrinho: um serviço + as áreas escolhidas (vazio se o serviço não
// tem áreas configuradas, ou se ainda não foram escolhidas).
export interface CartItem {
  service: Service
  areaIds: string[]
}

export type WizardStep = 'cart' | 'areas' | 'professional' | 'schedule' | 'customer' | 'success'
