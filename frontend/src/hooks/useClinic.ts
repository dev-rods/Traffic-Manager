import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { clinicService } from '@/services/clinic.service'
import type { UpdateClinicPayload } from '@/types'
import { useAuth } from './useAuth'

export const clinicKeys = {
  all: ['clinic'] as const,
  detail: (clinicId: string) => [...clinicKeys.all, clinicId] as const,
}

export function useClinic() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: clinicKeys.detail(clinicId!),
    queryFn: () => clinicService.get(clinicId!),
    enabled: !!clinicId,
  })
}

export function useUpdateClinic() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: UpdateClinicPayload) => clinicService.update(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: clinicKeys.all })
    },
  })
}
