import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { catalogService } from '@/services/catalog.service'
import type { DiscountRule } from '@/types'
import { useAuth } from './useAuth'

export const discountRuleKeys = {
  all: ['discount-rules'] as const,
  detail: (clinicId: string) => [...discountRuleKeys.all, clinicId] as const,
}

export function useDiscountRules() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: discountRuleKeys.detail(clinicId!),
    queryFn: () => catalogService.getDiscountRules(clinicId!),
    enabled: !!clinicId,
  })
}

export function useUpsertDiscountRules() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: Omit<DiscountRule, 'clinic_id'>) =>
      catalogService.upsertDiscountRules(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: discountRuleKeys.all })
    },
  })
}
