import { useQuery } from '@tanstack/react-query'
import { leadsService } from '@/services/leads.service'
import { useAuth } from './useAuth'

export const leadKeys = {
  all: ['leads'] as const,
  list: (clinicId: string, filters: Record<string, unknown>) => [...leadKeys.all, clinicId, filters] as const,
}

export function useLeads(params?: { startDate?: string; endDate?: string; booked?: boolean; limit?: number; offset?: number }) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: leadKeys.list(clinicId!, params ?? {}),
    queryFn: () => leadsService.list(clinicId!, params),
    enabled: !!clinicId,
    staleTime: 2 * 60 * 1000,
  })
}
