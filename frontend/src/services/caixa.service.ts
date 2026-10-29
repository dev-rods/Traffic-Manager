import { api } from './api'
import type { PaymentMethod, PaymentStatus } from '@/types'

export type ByMethod = Record<PaymentMethod, number>

export interface CaixaDay {
  date: string
  sessions: number
  /** Pela data da SESSÃO. */
  expectedCents: number
  /** Pela data em que o dinheiro ENTROU, no fuso da clínica. */
  receivedCents: number
  byMethod: ByMethod
}

export interface CaixaPending {
  appointmentId: string
  date: string
  startTime: string
  name: string | null
  amountCents: number
  checkedIn: boolean
  paymentId: string | null
  method: PaymentMethod | null
  paymentStatus: PaymentStatus | null
}

export interface CaixaPayment {
  id: string
  method: PaymentMethod
  amountCents: number
  paidAt: string
  appointmentDate: string
  startTime: string
  name: string | null
  simulated: boolean
  /** A sessão foi cancelada depois de paga: o dinheiro entrou e falta decidir o estorno. */
  appointmentCancelled: boolean
}

export interface CaixaResumo {
  dateFrom: string
  dateTo: string
  timezone: string
  totals: {
    expectedCents: number
    receivedCents: number
    pendingCents: number
    pendingCount: number
    refundsPendingCents: number
    byMethod: Record<PaymentMethod, { count: number; cents: number }>
  }
  days: CaixaDay[]
  pending: CaixaPending[]
  payments: CaixaPayment[]
  /** Pagos de sessões canceladas, de qualquer data: um estorno esquecido não some com o filtro. */
  refundsPending: CaixaPayment[]
}

export interface CaixaPaymentResult {
  id: string
  status: PaymentStatus
  /** Estorno: o Asaas aceitou o pedido, mas o dono da conta ainda precisa autorizar (token). */
  refundNeedsAuthorization?: boolean
}

export interface LinkDePagamento {
  payment: CaixaPaymentResult
  invoiceUrl: string
  /** false: a cobrança existe, mas o WhatsApp não foi. A recepção manda o link à mão. */
  sent: boolean
}

export const caixaService = {
  resumo: (clinicId: string, dateFrom: string, dateTo: string) =>
    api
      .get<CaixaResumo>(`/clinics/${clinicId}/caixa/resumo`, {
        params: { date_from: dateFrom, date_to: dateTo },
      })
      .then((r) => r.data),

  /** A recepção recebeu em dinheiro: dá baixa aqui e no Asaas. */
  receberDinheiro: (clinicId: string, paymentId: string) =>
    api
      .post<{
        payment: CaixaPaymentResult
      }>(`/clinics/${clinicId}/caixa/pagamentos/${paymentId}/dinheiro`)
      .then((r) => r.data.payment),

  /** Link de cobrança pelo WhatsApp para quem não pagou no check-in (PRD 029). */
  enviarLink: (clinicId: string, appointmentId: string, cpf?: string) =>
    api
      .post<LinkDePagamento>(
        `/clinics/${clinicId}/caixa/agendamentos/${appointmentId}/link`,
        cpf ? { cpf } : {}
      )
      .then((r) => r.data),

  /** Estorno de pagamento de sessão cancelada: Pix e cartão voltam pelo Asaas; dinheiro, em mão. */
  estornar: (clinicId: string, paymentId: string) =>
    api
      .post<{
        payment: CaixaPaymentResult
      }>(`/clinics/${clinicId}/caixa/pagamentos/${paymentId}/estorno`)
      .then((r) => r.data.payment),
}
