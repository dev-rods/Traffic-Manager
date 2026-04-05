import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { faqService } from '@/services/faq.service'
import type { CreateFaqPayload } from '@/types'
import { useAuth } from './useAuth'

export const faqKeys = {
  all: ['faq'] as const,
  list: (clinicId: string) => [...faqKeys.all, 'list', clinicId] as const,
}

export function useFaq() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: faqKeys.list(clinicId!),
    queryFn: () => faqService.list(clinicId!),
    enabled: !!clinicId,
  })
}

export function useCreateFaq() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateFaqPayload) => faqService.create(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: faqKeys.list(clinicId!) })
    },
  })
}

export function useUpdateFaq() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ faqId, payload }: { faqId: string; payload: Partial<CreateFaqPayload> & { active?: boolean } }) =>
      faqService.update(faqId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: faqKeys.list(clinicId!) })
    },
  })
}
