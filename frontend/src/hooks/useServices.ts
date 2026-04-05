import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { servicesService } from '@/services/services.service'
import type { CreateServicePayload, UpdateServicePayload } from '@/services/services.service'
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
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateService() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateServicePayload) => servicesService.create(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: serviceKeys.list(clinicId!) })
    },
  })
}

export function useUpdateService() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ serviceId, payload }: { serviceId: string; payload: UpdateServicePayload }) =>
      servicesService.update(serviceId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: serviceKeys.list(clinicId!) })
    },
  })
}
