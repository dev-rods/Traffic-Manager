export interface Clinic {
  clinic_id: string
  name: string
  display_name: string | null
  logo_url: string | null
  favicon_url: string | null
  timezone: string
  // Contato da clínica (só dígitos, com DDI) — botão de WhatsApp quando não
  // há mais horário no mês.
  phone: string | null
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

// Faixa de desconto por quantidade de áreas, como o backend a cobra. Só para
// anunciar: o desconto do carrinho continua vindo de /quote.
export interface DiscountTier {
  minAreas: number
  maxAreas: number | null
  pct: number
}

export interface BootstrapResponse {
  status: 'SUCCESS'
  clinic: Clinic
  services: Service[]
  professionals: Professional[]
  serviceAreas: ServiceArea[]
  discountTiers: DiscountTier[]
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

export interface ServiceAreaPair {
  serviceId: string
  areaId: string
}

// O carrinho como o backend o recebe — duração, preço e desconto são sempre
// calculados lá, a partir disto (mesma conta do bot de WhatsApp).
export interface CartPayload {
  serviceIds: string[]
  serviceAreaPairs: ServiceAreaPair[]
}

// Profissional não é escolhido pelo cliente: o backend atribui.
export interface CreateAppointmentPayload extends CartPayload {
  phone: string
  fullName: string
  date: string
  time: string
  // O número já tem agendamento futuro e a pessoa confirmou que quer manter
  // os dois. Sem isto, a criação responde 409 HAS_FUTURE_APPOINTMENT.
  confirmDuplicate?: boolean
}

export type DiscountReason = 'first_session' | 'tier_2' | 'tier_3' | 'personalizado'

export interface ComboApplied {
  from: string[]
  to: string
  savingsCents: number
}

// Resposta de POST /quote — o mesmo valor que a criação vai gravar.
export interface Quote {
  originalPriceCents: number | null
  discountPct: number
  discountReason: DiscountReason | null
  finalPriceCents: number | null
  areaCount: number
  combos: ComboApplied[]
}

// Status de um dia no seletor de semana — mesma lógica da AvailabilityEngine
// usada pelo bot: CLOSED (sem regra de agenda), FULL (regra existe, sem vaga),
// AVAILABLE (tem horário livre).
export type DayAvailabilityStatus = 'CLOSED' | 'FULL' | 'AVAILABLE'

export interface DayAvailability {
  status: DayAvailabilityStatus
  slots: string[]
}

// As próximas N datas com horário, em ordem (N = "Datas futuras" da clínica,
// no fuso dela) — a regra mora no backend; o front só exibe.
export interface AvailabilityResponse {
  days: Record<string, DayAvailability>
}

// Item do carrinho: um serviço + as áreas escolhidas (vazio se o serviço não
// tem áreas configuradas, ou se ainda não foram escolhidas).
export interface CartItem {
  service: Service
  areaIds: string[]
}

export type WizardStep = 'cart' | 'areas' | 'schedule' | 'customer' | 'success'
