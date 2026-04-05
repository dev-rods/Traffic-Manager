import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { areasService } from '@/services/areas.service'
import type { CreateAreaPayload } from '@/types'
import type { CreateServiceAreaPayload } from '@/services/areas.service'
import { useAuth } from './useAuth'

export const areaKeys = {
  all: ['areas'] as const,
  clinicList: (clinicId: string) => [...areaKeys.all, 'clinic', clinicId] as const,
  byService: (serviceId: string) => [...areaKeys.all, 'service', serviceId] as const,
}

export function useClinicAreas() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: areaKeys.clinicList(clinicId!),
    queryFn: () => areasService.listClinicAreas(clinicId!),
    enabled: !!clinicId,
  })
}

export function useCreateArea() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: CreateAreaPayload) => areasService.createArea(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: areaKeys.clinicList(clinicId!) })
    },
  })
}

export function useUpdateArea() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ areaId, payload }: { areaId: string; payload: Partial<CreateAreaPayload> & { active?: boolean } }) =>
      areasService.updateArea(areaId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: areaKeys.clinicList(clinicId!) })
      queryClient.invalidateQueries({ queryKey: areaKeys.all })
    },
  })
}

export function useDeleteArea() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (areaId: string) => areasService.deleteArea(areaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: areaKeys.clinicList(clinicId!) })
      queryClient.invalidateQueries({ queryKey: areaKeys.all })
    },
  })
}

export function useServiceAreas(serviceId: string | undefined) {
  return useQuery({
    queryKey: areaKeys.byService(serviceId!),
    queryFn: () => areasService.listByService(serviceId!),
    enabled: !!serviceId,
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateServiceArea() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ serviceId, payload }: { serviceId: string; payload: CreateServiceAreaPayload }) =>
      areasService.createServiceArea(serviceId, payload),
    onSuccess: (_data, { serviceId }) => {
      queryClient.invalidateQueries({ queryKey: areaKeys.byService(serviceId) })
    },
  })
}

export function useUpdateServiceArea() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ serviceId, areaId, payload }: { serviceId: string; areaId: string; payload: { duration_minutes?: number | null; price_cents?: number | null; pre_session_instructions?: string | null } }) =>
      areasService.updateServiceArea(serviceId, areaId, payload),
    onSuccess: (_data, { serviceId }) => {
      queryClient.invalidateQueries({ queryKey: areaKeys.byService(serviceId) })
    },
  })
}

export function useDeleteServiceArea() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ serviceId, areaId }: { serviceId: string; areaId: string }) =>
      areasService.deleteServiceArea(serviceId, areaId),
    onSuccess: (_data, { serviceId }) => {
      queryClient.invalidateQueries({ queryKey: areaKeys.byService(serviceId) })
    },
  })
}
