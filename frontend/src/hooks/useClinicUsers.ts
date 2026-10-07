import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clinicUsersService } from '@/services/clinicUsers.service'
import type { AlteracaoDeUsuario } from '@/services/clinicUsers.service'
import { useAuth } from './useAuth'

export const usuarioKeys = {
  all: ['clinic-users'] as const,
  list: (clinicId: string) => [...usuarioKeys.all, 'list', clinicId] as const,
}

export function useClinicUsers() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: usuarioKeys.list(clinicId ?? ''),
    queryFn: () => clinicUsersService.list(clinicId as string),
    enabled: Boolean(clinicId),
  })
}

export function useUpdateClinicUser() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ userId, dados }: { userId: string; dados: AlteracaoDeUsuario }) =>
      clinicUsersService.update(clinicId as string, userId, dados),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: usuarioKeys.all })
    },
  })
}
