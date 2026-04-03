import { useQuery } from '@tanstack/react-query'
import { availabilityService } from '@/services/availability.service'
import { useAuth } from './useAuth'

export const availabilityRuleKeys = {
  all: ['availability-rules'] as const,
  lists: () => [...availabilityRuleKeys.all, 'list'] as const,
  list: (clinicId: string) => [...availabilityRuleKeys.lists(), clinicId] as const,
}

export const slotKeys = {
  all: ['available-slots'] as const,
  slot: (clinicId: string, date: string, serviceId: string, totalDuration?: number) =>
    [...slotKeys.all, clinicId, date, serviceId, totalDuration] as const,
}

export function useAvailabilityRules() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: availabilityRuleKeys.list(clinicId!),
    queryFn: () => availabilityService.listRules(clinicId!),
    enabled: !!clinicId,
    staleTime: 5 * 60 * 1000, // rules rarely change — cache 5 min
  })
}

export function useAvailableSlots(date: string | undefined, serviceId: string | undefined, totalDuration?: number) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: slotKeys.slot(clinicId!, date!, serviceId!, totalDuration),
    queryFn: () => availabilityService.getSlots(clinicId!, date!, serviceId!, totalDuration),
    enabled: !!clinicId && !!date && !!serviceId,
  })
}
