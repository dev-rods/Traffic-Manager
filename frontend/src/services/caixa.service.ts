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
    byMethod: Record<PaymentMethod, { count: number; cents: number }>
  }
  days: CaixaDay[]
  pending: CaixaPending[]
  payments: CaixaPayment[]
}

export interface CaixaPaymentResult {
  id: string
  status: PaymentStatus
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
      .post<{ payment: CaixaPaymentResult }>(
        `/clinics/${clinicId}/caixa/pagamentos/${paymentId}/dinheiro`,
      )
      .then((r) => r.data.payment),
}
