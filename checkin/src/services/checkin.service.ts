import { api } from './api'
import type {
  BootstrapResponse,
  CheckinAppointment,
  Payment,
  PaymentMethod,
  Session,
} from '@/types'

const base = (clinicId: string) => `/public/clinics/${clinicId}`

export const checkinService = {
  bootstrap: (clinicId: string) =>
    api.get<BootstrapResponse>(`${base(clinicId)}/bootstrap`).then((r) => r.data),

  // O mesmo código por WhatsApp de "Meus agendamentos" no site.
  sendCode: (clinicId: string, phone: string) =>
    api.post(`${base(clinicId)}/verify/send`, { phone }).then(() => undefined),

  confirmCode: (clinicId: string, phone: string, code: string) =>
    api
      .post<{ token: string }>(`${base(clinicId)}/verify/confirm`, { phone, code })
      .then((r) => r.data.token),

  appointments: (clinicId: string, s: Session) =>
    api
      .get<{ appointments: CheckinAppointment[] }>(`${base(clinicId)}/checkin/appointments`, {
        params: s,
      })
      .then((r) => r.data.appointments),

  confirm: (clinicId: string, s: Session, appointmentId: string) =>
    api
      .post<{
        payerCpfKnown: boolean
      }>(`${base(clinicId)}/checkin/appointments/${appointmentId}/confirm`, s)
      .then((r) => r.data),

  pay: (clinicId: string, s: Session, appointmentId: string, method: PaymentMethod, cpf?: string) =>
    api
      .post<{
        payment: Payment
      }>(`${base(clinicId)}/checkin/appointments/${appointmentId}/payments`, { ...s, method, cpf })
      .then((r) => r.data.payment),

  payment: (clinicId: string, s: Session, paymentId: string) =>
    api
      .get<{ payment: Payment }>(`${base(clinicId)}/checkin/payments/${paymentId}`, { params: s })
      .then((r) => r.data.payment),

  simulate: (clinicId: string, s: Session, paymentId: string) =>
    api
      .post<{ payment: Payment }>(`${base(clinicId)}/checkin/payments/${paymentId}/simulate`, s)
      .then((r) => r.data.payment),
}
