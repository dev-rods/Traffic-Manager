import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { consentsService } from '@/services/consents.service'
import type { ConsentWaiveReason } from '@/types'
import { useAuth } from './useAuth'
import { appointmentKeys } from './useAppointments'

export const consentKeys = {
  all: ['consents'] as const,
  byPatient: (clinicId: string, patientId: string) =>
    [...consentKeys.all, 'patient', clinicId, patientId] as const,
}

export function useConsentsDoPaciente(patientId: string | undefined) {
  const { clinicId } = useAuth()
  return useQuery({
    queryKey: consentKeys.byPatient(clinicId!, patientId!),
    queryFn: () => consentsService.listByPatient(clinicId!, patientId!),
    enabled: !!clinicId && !!patientId,
  })
}

/** Dispensa nesta sessão. A agenda muda junto: o selo "TERMO" some. */
export function useDispensarTermo() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (v: { appointmentId: string; reason: ConsentWaiveReason; note?: string }) =>
      consentsService.waive(clinicId!, v.appointmentId, v.reason, v.note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
      queryClient.invalidateQueries({ queryKey: consentKeys.all })
    },
  })
}

export function useRegistrarPapel() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (v: { patientId: string; signedAt: string }) =>
      consentsService.registerPaper(clinicId!, v.patientId, v.signedAt),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
      queryClient.invalidateQueries({ queryKey: consentKeys.all })
    },
  })
}

/** "Pedir nova assinatura": a agenda volta a mostrar DOCS para a paciente. */
export function useRenovarTermo() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (consentId: string) => consentsService.renew(clinicId!, consentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
      queryClient.invalidateQueries({ queryKey: consentKeys.all })
    },
  })
}

/**
 * Abre o PDF (ou o zip) numa aba nova. É mutação, não query: a URL expira em
 * 5 min e não pode ficar em cache.
 */
export function useAbrirDocumentoDoTermo() {
  const { clinicId } = useAuth()
  return useMutation({
    mutationFn: (v: { consentId: string; kind: 'pdf' | 'zip' }) =>
      v.kind === 'pdf'
        ? consentsService.pdfUrl(clinicId!, v.consentId)
        : consentsService.zipUrl(clinicId!, v.consentId),
    onSuccess: ({ url }) => {
      window.open(url, '_blank', 'noopener')
    },
  })
}
