import { useQuery } from '@tanstack/react-query'
import { areasService } from '@/services/areas.service'

export const areaKeys = {
  all: ['areas'] as const,
  byService: (serviceId: string) => [...areaKeys.all, 'service', serviceId] as const,
}

export function useServiceAreas(serviceId: string | undefined) {
  return useQuery({
    queryKey: areaKeys.byService(serviceId!),
    queryFn: () => areasService.listByService(serviceId!),
    enabled: !!serviceId,
    staleTime: 5 * 60 * 1000,
  })
}
