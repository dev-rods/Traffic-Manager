import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { patientsService } from '@/services/patients.service'
import type { ListPatientsParams } from '@/services/patients.service'
import type { CreatePatientPayload } from '@/types'
import { useAuth } from './useAuth'

export const patientKeys = {
  all: ['patients'] as const,
  lists: () => [...patientKeys.all, 'list'] as const,
  list: (clinicId: string, params?: ListPatientsParams) =>
    [...patientKeys.lists(), clinicId, params] as const,
}

export function usePatients(params?: ListPatientsParams) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: patientKeys.list(clinicId!, params),
    queryFn: () => patientsService.list(clinicId!, params),
    enabled: !!clinicId,
  })
}

export function useCreatePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreatePatientPayload) => patientsService.create(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}

export function useUpdatePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ patientId, data }: { patientId: string; data: Partial<CreatePatientPayload> }) =>
      patientsService.update(clinicId!, patientId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}
