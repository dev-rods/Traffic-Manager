import { useCallback, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { consentsService } from '@/services/consents.service'
import type { ConsentWaiveReason } from '@/types'
import { useAuth } from './useAuth'
import { appointmentKeys } from './useAppointments'
import { patientKeys } from './usePatients'

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
      // A lista de pacientes mostra o selo "Sem termo" (PRD 047).
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}

export interface ResultadoDoPapelEmLote {
  patientId: string
  status: 'pending' | 'registered' | 'already' | 'failed'
  error?: string
}

/**
 * "Assinado em papel" para várias pessoas, com UMA data (PRD 047, §7.2 B).
 *
 * Mesmo molde do excluir em lote: laço sequencial sobre a rota unitária,
 * progresso e resultado por pessoa. `already` é quem já tinha termo vigente -
 * o servidor devolve o que havia e não grava.
 */
export function useRegistrarPapelEmLote() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  const [results, setResults] = useState<ResultadoDoPapelEmLote[]>([])
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState({ done: 0, total: 0 })
  const runningRef = useRef(false)

  const run = useCallback(
    async (patientIds: string[], signedAt: string) => {
      if (!clinicId || patientIds.length === 0 || !signedAt) return
      if (runningRef.current) return
      runningRef.current = true

      setIsRunning(true)
      setProgress({ done: 0, total: patientIds.length })
      setResults(patientIds.map((id) => ({ patientId: id, status: 'pending' as const })))

      for (let i = 0; i < patientIds.length; i++) {
        const id = patientIds[i]
        try {
          const { created } = await consentsService.registerPaper(clinicId, id, signedAt)
          setResults((prev) =>
            prev.map((r) =>
              r.patientId === id ? { ...r, status: created ? 'registered' : 'already' } : r
            )
          )
        } catch (err: unknown) {
          const message =
            (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
            (err instanceof Error ? err.message : 'Erro desconhecido')
          setResults((prev) =>
            prev.map((r) => (r.patientId === id ? { ...r, status: 'failed', error: message } : r))
          )
        }
        setProgress({ done: i + 1, total: patientIds.length })
      }

      setIsRunning(false)
      runningRef.current = false
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
      queryClient.invalidateQueries({ queryKey: consentKeys.all })
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
    },
    [clinicId, queryClient]
  )

  const reset = useCallback(() => {
    setResults([])
    setProgress({ done: 0, total: 0 })
  }, [])

  return { run, results, isRunning, progress, reset }
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
