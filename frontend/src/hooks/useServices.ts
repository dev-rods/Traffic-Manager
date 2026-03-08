import { useQuery } from '@tanstack/react-query'
import { servicesService } from '@/services/services.service'
import { useAuth } from './useAuth'

export const serviceKeys = {
  all: ['services'] as const,
  list: (clinicId: string) => [...serviceKeys.all, 'list', clinicId] as const,
}

export function useServices() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: serviceKeys.list(clinicId!),
    queryFn: () => servicesService.list(clinicId!),
    enabled: !!clinicId,
    staleTime: 5 * 60 * 1000, // services rarely change
  })
}
