import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { professionalsService, type UpdateProfessionalPayload } from '@/services/professionals.service'
import { useAuth } from './useAuth'

export const professionalKeys = {
  all: ['professionals'] as const,
  list: (clinicId: string) => [...professionalKeys.all, 'list', clinicId] as const,
}

export function useProfessionals() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: professionalKeys.list(clinicId!),
    queryFn: () => professionalsService.list(clinicId!),
    enabled: !!clinicId,
    staleTime: 5 * 60 * 1000,
  })
}

/** Registro no conselho (e nome/cargo) pelo painel; só admin (PRD 036). */
export function useUpdateProfessional() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateProfessionalPayload }) =>
      professionalsService.update(clinicId!, id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: professionalKeys.all })
    },
  })
}
