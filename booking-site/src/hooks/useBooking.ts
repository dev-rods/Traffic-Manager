import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { bookingService } from '@/services/booking.service'
import type { CreateAppointmentPayload } from '@/types'

export const bookingKeys = {
  all: ['booking'] as const,
  bootstrap: (clinicId: string) => [...bookingKeys.all, 'bootstrap', clinicId] as const,
  slots: (clinicId: string, date: string, serviceId: string, totalDuration: number) =>
    [...bookingKeys.all, 'slots', clinicId, date, serviceId, totalDuration] as const,
  myAppointments: (clinicId: string, phone: string) =>
    [...bookingKeys.all, 'my-appointments', clinicId, phone] as const,
}

export function useClinicBootstrap(clinicId: string) {
  return useQuery({
    queryKey: bookingKeys.bootstrap(clinicId),
    queryFn: () => bookingService.bootstrap(clinicId),
    staleTime: 1000 * 60 * 5,
    retry: 1,
  })
}

export function useAvailableSlots(
  clinicId: string,
  date: string | null,
  serviceId: string,
  totalDuration: number
) {
  return useQuery({
    queryKey: bookingKeys.slots(clinicId, date ?? '', serviceId, totalDuration),
    queryFn: () => bookingService.availableSlots(clinicId, { date: date as string, serviceId, totalDuration }),
    enabled: Boolean(date && serviceId && totalDuration > 0),
  })
}

export function useSendOtp(clinicId: string) {
  return useMutation({
    mutationFn: (phone: string) => bookingService.sendOtp(clinicId, phone),
  })
}

export function useConfirmOtp(clinicId: string) {
  return useMutation({
    mutationFn: ({ phone, code }: { phone: string; code: string }) =>
      bookingService.confirmOtp(clinicId, phone, code),
  })
}

export function useCreateAppointment(clinicId: string) {
  return useMutation({
    mutationFn: (payload: CreateAppointmentPayload) => bookingService.createAppointment(clinicId, payload),
  })
}

export function useMyAppointments(clinicId: string, phone: string, token: string | null) {
  return useQuery({
    queryKey: bookingKeys.myAppointments(clinicId, phone),
    queryFn: () => bookingService.myAppointments(clinicId, phone, token as string),
    enabled: Boolean(token && phone),
  })
}

export function useCancelAppointment(clinicId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ appointmentId, phone, token }: { appointmentId: string; phone: string; token: string }) =>
      bookingService.cancelAppointment(clinicId, appointmentId, phone, token),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: bookingKeys.myAppointments(clinicId, variables.phone) })
    },
  })
}
