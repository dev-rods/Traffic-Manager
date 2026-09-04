import { useQuery } from '@tanstack/react-query'
import { leadsService, type LeadListParams } from '@/services/leads.service'
import { useAuth } from './useAuth'

export const leadKeys = {
  all: ['leads'] as const,
  list: (clinicId: string, filters: LeadListParams) => [...leadKeys.all, clinicId, filters] as const,
}

export function useLeads(params?: LeadListParams) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: leadKeys.list(clinicId!, params ?? {}),
    queryFn: () => leadsService.list(clinicId!, params),
    enabled: !!clinicId,
    staleTime: 2 * 60 * 1000,
  })
}
