import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { availabilityService } from '@/services/availability.service'
import type { CreateAvailabilityRulePayload, CreateAvailabilityExceptionPayload } from '@/types'
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

export function useDeleteAvailabilityRule() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (ruleId: string) => availabilityService.deleteRule(ruleId),
    onSuccess: () => {
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

export function useAvailableSlots(date: string | undefined, serviceId: string | undefined, totalDuration?: number) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: slotKeys.slot(clinicId!, date!, serviceId!, totalDuration),
    queryFn: () => availabilityService.getSlots(clinicId!, date!, serviceId!, totalDuration),
    enabled: !!clinicId && !!date && !!serviceId,
  })
}
