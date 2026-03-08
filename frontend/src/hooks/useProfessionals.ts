import { useQuery } from '@tanstack/react-query'
import { professionalsService } from '@/services/professionals.service'
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
