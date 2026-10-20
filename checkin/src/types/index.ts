export interface Clinic {
  clinic_id: string
  name: string
  display_name: string | null
  logo_url: string | null
}

export interface BootstrapResponse {
  clinic: Clinic
}

export type PaymentMethod = 'PIX' | 'CREDIT_CARD' | 'DEBIT_CARD' | 'CASH'

export type PaymentStatus =
  | 'PENDING'
  | 'AWAITING_CASH'
  | 'PAID'
  | 'CANCELLED'
  | 'FAILED'
  | 'REFUNDED'

export interface Payment {
  id: string
  method: PaymentMethod
  status: PaymentStatus
  amountCents: number
  invoiceUrl: string | null
  pixPayload: string | null
  paidAt: string | null
  // Provedor simulado (só dev, sem conta no Asaas): o pagamento é confirmado
  // por um botão, não pelo banco.
  simulated: boolean
}

export interface CheckinAppointment {
  id: string
  date: string
  startTime: string
  fullName: string | null
  serviceName: string | null
  areas: string[]
  originalPriceCents: number | null
  finalPriceCents: number | null
  discountPct: number
  checkedInAt: string | null
  payment: Payment | null
}

export interface Session {
  phone: string
  token: string
}
