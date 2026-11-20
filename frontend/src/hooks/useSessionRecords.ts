import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { sessionRecordsService } from '@/services/sessionRecords.service'
import type { RegistroPayload } from '@/types'
import { useAuth } from './useAuth'

export const sessionRecordKeys = {
  all: ['session-records'] as const,
  list: (clinicId: string, patientId: string) =>
    [...sessionRecordKeys.all, clinicId, patientId] as const,
  history: (clinicId: string, recordId: string) =>
    [...sessionRecordKeys.all, 'history', clinicId, recordId] as const,
  aplicacoes: (clinicId: string, appointmentId: string) =>
    [...sessionRecordKeys.all, 'aplicacoes', clinicId, appointmentId] as const,
}

/**
 * Busca imperativa das aplicações do agendamento (PRD 051).
 *
 * É chamada de um evento (escolher a sessão no seletor), não de render, por
 * isso devolve uma função e não um `useQuery`. Passa pelo cache: trocar de
 * sessão e voltar não bate no servidor de novo.
 */
export function useAplicacoesDoAgendamento() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return (appointmentId: string) =>
    queryClient.fetchQuery({
      queryKey: sessionRecordKeys.aplicacoes(clinicId!, appointmentId),
      queryFn: () => sessionRecordsService.aplicacoesDoAgendamento(clinicId!, appointmentId),
      staleTime: 60_000,
    })
}

export function useSessionRecords(patientId: string | undefined) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: sessionRecordKeys.list(clinicId!, patientId!),
    queryFn: () => sessionRecordsService.list(clinicId!, patientId!),
    enabled: !!clinicId && !!patientId,
  })
}

export function useSessionRecordHistory(recordId: string | undefined) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: sessionRecordKeys.history(clinicId!, recordId!),
    queryFn: () => sessionRecordsService.history(clinicId!, recordId!),
    enabled: !!clinicId && !!recordId,
  })
}

export function useCreateSessionRecord(patientId: string) {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: RegistroPayload) =>
      sessionRecordsService.create(clinicId!, patientId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionRecordKeys.all })
    },
  })
}

export function useUpdateSessionRecord() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ recordId, payload }: { recordId: string; payload: RegistroPayload }) =>
      sessionRecordsService.update(clinicId!, recordId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionRecordKeys.all })
    },
  })
}

export function useDeleteSessionRecord() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (recordId: string) => sessionRecordsService.remove(clinicId!, recordId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionRecordKeys.all })
    },
  })
}
