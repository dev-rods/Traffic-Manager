import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { availabilityService } from '@/services/availability.service'
import type { ListAvailabilityRulesResponse } from '@/services/availability.service'
import type {
  AvailabilityException,
  CreateAvailabilityRulePayload,
  CreateAvailabilityExceptionPayload,
  UpdateAvailabilityRulePayload,
} from '@/types'
import { useAuth } from './useAuth'

export const availabilityRuleKeys = {
  all: ['availability-rules'] as const,
  lists: () => [...availabilityRuleKeys.all, 'list'] as const,
  list: (clinicId: string) => [...availabilityRuleKeys.lists(), clinicId] as const,
}

export const exceptionKeys = {
  all: ['availability-exceptions'] as const,
  list: (clinicId: string) => [...exceptionKeys.all, 'list', clinicId] as const,
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
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateAvailabilityRule() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateAvailabilityRulePayload) =>
      availabilityService.createRule(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityRuleKeys.list(clinicId!) })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
    },
  })
}

export function useUpdateAvailabilityRule() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ ruleId, payload }: { ruleId: string; payload: UpdateAvailabilityRulePayload }) =>
      availabilityService.updateRule(clinicId!, ruleId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: availabilityRuleKeys.list(clinicId!) })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
    },
  })
}

export function useDeleteAvailabilityRule() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (ruleId: string) => availabilityService.deleteRule(clinicId!, ruleId),
    onMutate: async (ruleId) => {
      // Obrigatorio: sem cancelar, um refetch em voo repoe o item excluido.
      await queryClient.cancelQueries({ queryKey: availabilityRuleKeys.list(clinicId!) })

      const previous = queryClient.getQueryData<ListAvailabilityRulesResponse>(
        availabilityRuleKeys.list(clinicId!),
      )

      queryClient.setQueryData<ListAvailabilityRulesResponse>(
        availabilityRuleKeys.list(clinicId!),
        (old) => (old ? { ...old, data: old.data.filter((r) => r.id !== ruleId) } : old),
      )

      return { previous }
    },
    onError: (_error, _ruleId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(availabilityRuleKeys.list(clinicId!), context.previous)
      }
    },
    // Em onSettled, nao onSuccess: precisa reconciliar com o servidor tambem no erro.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: availabilityRuleKeys.list(clinicId!) })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
    },
  })
}

export function useAvailabilityExceptions() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: exceptionKeys.list(clinicId!),
    queryFn: () => availabilityService.listExceptions(clinicId!),
    enabled: !!clinicId,
  })
}

export function useCreateAvailabilityException() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateAvailabilityExceptionPayload) =>
      availabilityService.createException(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: exceptionKeys.list(clinicId!) })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
    },
  })
}

export function useDeleteAvailabilityException() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (exceptionId: string) =>
      availabilityService.deleteException(clinicId!, exceptionId),
    onMutate: async (exceptionId) => {
      await queryClient.cancelQueries({ queryKey: exceptionKeys.list(clinicId!) })

      // Diferente das rules: listExceptions devolve o array direto, sem envelope.
      const previous = queryClient.getQueryData<AvailabilityException[]>(
        exceptionKeys.list(clinicId!),
      )

      queryClient.setQueryData<AvailabilityException[]>(exceptionKeys.list(clinicId!), (old) =>
        old ? old.filter((e) => e.id !== exceptionId) : old,
      )

      return { previous }
    },
    onError: (_error, _exceptionId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(exceptionKeys.list(clinicId!), context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: exceptionKeys.list(clinicId!) })
      queryClient.invalidateQueries({ queryKey: slotKeys.all })
    },
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
