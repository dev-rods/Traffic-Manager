export interface Clinic {
  clinic_id: string
  name: string
  display_name: string | null
  logo_url: string | null
}

export interface BootstrapResponse {
  clinic: Clinic
}

// LINK: cobrança mandada pela recepção no WhatsApp (PRD 029); não é escolha do iPad.
export type PaymentMethod = 'PIX' | 'CREDIT_CARD' | 'DEBIT_CARD' | 'CASH' | 'LINK'

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
  // Cobrança de teste (dev: provedor simulado ou Asaas sandbox). Não movimenta
  // dinheiro de verdade.
  simulated: boolean
  // O botão "Simular pagamento (teste)" vale para esta cobrança. No sandbox
  // do Asaas só para Pix: cartão se testa pagando a fatura com cartão de teste.
  canSimulate: boolean
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
  // Termo de consentimento (PRD 036). Quem decide "precisa assinar" é o
  // backend; o iPad só pede quando ele manda.
  consentRequired: boolean
  consentPrefill: ConsentPrefill | null
}

export interface ConsentGuardianPrefill {
  name: string
  cpfMasked: string | null
  birthDate: string | null
  phone: string | null
  email: string | null
}

export interface ConsentPrefill {
  name: string | null
  // CPF conhecido vem mascarado (`***.***.***-12`); `cpfKnown` diz se a tela
  // pode pular o campo. `cpf: null` no envio significa "manter o conhecido".
  cpfMasked: string | null
  cpfKnown: boolean
  birthDate: string | null
  phone: string | null
  email: string | null
  isMinor: boolean
  // Responsável, cidade e registro cadastrados: sem isso o termo não é gerado.
  clinicReady: boolean
  guardian: ConsentGuardianPrefill | null
}

export type ConsentStatus = 'NOT_REQUIRED' | 'SIGNING' | 'SIGNED' | 'CANCELLED' | 'EXPIRED'

export interface Consent {
  id: string | null
  status: ConsentStatus
  signerId: string | null
  // Onde o widget carrega (sandbox ou produção da ClickSign); vazio no simulado.
  widgetEndpoint: string
  // Termo de teste (sandbox ou simulado): sem valor jurídico, a tela marca.
  test: boolean
  canSimulate: boolean
  signedAt: string | null
}

export interface ConsentGuardianPayload {
  name: string
  cpf: string
  birthDate: string
  phone: string
  email: string
}

export interface ConsentStartPayload {
  fullName: string
  cpf: string | null
  birthDate: string
  email: string
  imageAuthorized: boolean
  guardian: ConsentGuardianPayload | null
}

export interface ConfirmResponse {
  payerCpfKnown: boolean
  consentRequired: boolean
  consentPrefill: ConsentPrefill | null
}

export interface Session {
  phone: string
  token: string
}
