import { useMutation, useQuery } from '@tanstack/react-query'
import { checkinService } from '@/services/checkin.service'
import type { ConsentStartPayload, PaymentMethod, Session } from '@/types'

export const checkinKeys = {
  bootstrap: (clinicId: string) => ['checkin', 'bootstrap', clinicId] as const,
  appointments: (clinicId: string, phone: string) =>
    ['checkin', 'appointments', clinicId, phone] as const,
  payment: (clinicId: string, paymentId: string) =>
    ['checkin', 'payment', clinicId, paymentId] as const,
  consent: (clinicId: string, consentId: string) =>
    ['checkin', 'consent', clinicId, consentId] as const,
}

export function useClinic(clinicId: string) {
  return useQuery({
    queryKey: checkinKeys.bootstrap(clinicId),
    queryFn: () => checkinService.bootstrap(clinicId),
    select: (data) => data.clinic,
    staleTime: 1000 * 60 * 30,
  })
}

export function useSendCode(clinicId: string) {
  return useMutation({ mutationFn: (phone: string) => checkinService.sendCode(clinicId, phone) })
}

export function useConfirmCode(clinicId: string) {
  return useMutation({
    mutationFn: ({ phone, code }: { phone: string; code: string }) =>
      checkinService.confirmCode(clinicId, phone, code),
  })
}

export function useAppointments(clinicId: string, session: Session | null) {
  return useQuery({
    queryKey: checkinKeys.appointments(clinicId, session?.phone ?? ''),
    queryFn: () => checkinService.appointments(clinicId, session as Session),
    enabled: session !== null,
    // Cada check-in é uma pessoa nova no balcão: nada de cache entre elas.
    staleTime: 0,
    gcTime: 0,
  })
}

export function useConfirmAppointment(clinicId: string, session: Session | null) {
  return useMutation({
    mutationFn: (appointmentId: string) =>
      checkinService.confirm(clinicId, session as Session, appointmentId),
  })
}

export function usePay(clinicId: string, session: Session | null) {
  return useMutation({
    mutationFn: (v: { appointmentId: string; method: PaymentMethod; cpf?: string }) =>
      checkinService.pay(clinicId, session as Session, v.appointmentId, v.method, v.cpf),
  })
}

const WAITING = new Set(['PENDING', 'AWAITING_CASH'])

/** Acompanha o pagamento até sair de pendente: o iPad confirma sozinho. */
export function usePaymentStatus(clinicId: string, session: Session | null, paymentId: string) {
  return useQuery({
    queryKey: checkinKeys.payment(clinicId, paymentId),
    queryFn: () => checkinService.payment(clinicId, session as Session, paymentId),
    enabled: session !== null,
    refetchInterval: (query) =>
      query.state.data && !WAITING.has(query.state.data.status) ? false : 3000,
    refetchIntervalInBackground: true,
    gcTime: 0,
  })
}

export function useSimulatePayment(clinicId: string, session: Session | null) {
  return useMutation({
    mutationFn: (paymentId: string) =>
      checkinService.simulate(clinicId, session as Session, paymentId),
  })
}

// Termo de consentimento (PRD 036) -------------------------------------------

export function useStartConsent(clinicId: string, session: Session | null) {
  return useMutation({
    mutationFn: (v: { appointmentId: string; payload: ConsentStartPayload }) =>
      checkinService.startConsent(clinicId, session as Session, v.appointmentId, v.payload),
  })
}

/** Acompanha a assinatura até sair de SIGNING: o webhook da ClickSign ou a
 * consulta que o backend faz a cada polling fecham o termo. */
export function useConsentStatus(clinicId: string, session: Session | null, consentId: string) {
  return useQuery({
    queryKey: checkinKeys.consent(clinicId, consentId),
    queryFn: () => checkinService.consent(clinicId, session as Session, consentId),
    enabled: session !== null,
    refetchInterval: (query) =>
      query.state.data && query.state.data.status !== 'SIGNING' ? false : 3000,
    refetchIntervalInBackground: true,
    gcTime: 0,
  })
}

export function useSimulateConsent(clinicId: string, session: Session | null) {
  return useMutation({
    mutationFn: (consentId: string) =>
      checkinService.simulateConsent(clinicId, session as Session, consentId),
  })
}
