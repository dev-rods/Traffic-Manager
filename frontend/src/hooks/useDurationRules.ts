import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { catalogService } from '@/services/catalog.service'
import type { DurationRule } from '@/types'
import { useAuth } from './useAuth'

export const durationRuleKeys = {
  all: ['duration-rules'] as const,
  detail: (clinicId: string) => [...durationRuleKeys.all, clinicId] as const,
}

export function useDurationRules() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: durationRuleKeys.detail(clinicId!),
    queryFn: () => catalogService.getDurationRules(clinicId!),
    enabled: !!clinicId,
  })
}

export function useUpdateDurationRules() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: Partial<Omit<DurationRule, 'clinic_id'>>) =>
      catalogService.updateDurationRules(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: durationRuleKeys.all })
    },
  })
}
