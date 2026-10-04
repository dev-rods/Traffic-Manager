import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { appointmentsService } from '@/services/appointments.service'
import type { ListAppointmentsParams } from '@/services/appointments.service'
import type { CreateAppointmentPayload, UpdateAppointmentPayload } from '@/types'
import { useAuth } from './useAuth'
import { slotKeys } from './useAvailabilityRules'
import { dashboardKeys } from './useDashboard'

export const appointmentKeys = {
  all: ['appointments'] as const,
  lists: () => [...appointmentKeys.all, 'list'] as const,
  list: (clinicId: string, params?: ListAppointmentsParams) =>
    [...appointmentKeys.lists(), clinicId, params] as const,
}

export function useAppointments(params?: ListAppointmentsParams) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: appointmentKeys.list(clinicId!, params),
    queryFn: () => appointmentsService.list(clinicId!, params),
    enabled: !!clinicId,
  })
}

export function useCreateAppointment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateAppointmentPayload) => appointmentsService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
    },
  })
}

export function useUpdateAppointment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ appointmentId, payload }: { appointmentId: string; payload: UpdateAppointmentPayload }) =>
      appointmentsService.update(appointmentId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
    },
  })
}

export function useCancelAppointment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (appointmentId: string) => appointmentsService.cancel(appointmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
      queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
    },
  })
}

// As MESMAS tres chaves do cancelamento. A falta nao libera horario, entao
// `slotKeys` nao muda por causa dela - mas invalidar de menos e o defeito que
// nao aparece em teste e aparece na tela da atendente, e o custo e um refetch.
function invalidaAgenda(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
  queryClient.invalidateQueries({ queryKey: slotKeys.all })
  queryClient.invalidateQueries({ queryKey: dashboardKeys.all })
}

export function useMarcarFalta() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (appointmentId: string) => appointmentsService.marcarFalta(appointmentId),
    onSuccess: () => invalidaAgenda(queryClient),
  })
}

export function useDesmarcarFalta() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (appointmentId: string) => appointmentsService.desmarcarFalta(appointmentId),
    onSuccess: () => invalidaAgenda(queryClient),
  })
}
