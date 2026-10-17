import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { bookingService } from '@/services/booking.service'
import type { CartPayload, CreateAppointmentPayload } from '@/types'

// Chave estável do carrinho: os mesmos serviços/áreas na mesma ordem dão a
// mesma consulta (a ordem importa — o primeiro serviço é o principal).
function cartKey(cart: CartPayload): string {
  return `${cart.serviceIds.join(',')}|${cart.serviceAreaPairs.map((p) => `${p.serviceId}:${p.areaId}`).join(',')}`
}

export const bookingKeys = {
  all: ['booking'] as const,
  bootstrap: (clinicId: string) => [...bookingKeys.all, 'bootstrap', clinicId] as const,
  availabilityAll: (clinicId: string) => [...bookingKeys.all, 'availability', clinicId] as const,
  availability: (clinicId: string, dates: string[], cart: CartPayload) =>
    [...bookingKeys.availabilityAll(clinicId), dates.join(','), cartKey(cart)] as const,
  quote: (clinicId: string, cart: CartPayload, phone: string | undefined) =>
    [...bookingKeys.all, 'quote', clinicId, cartKey(cart), phone ?? ''] as const,
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

/**
 * Dias e horários do mês vigente para o carrinho. `enabled` falso enquanto há
 * área pendente de escolha — sem ela a duração (e a grade) ainda não existe.
 * `staleTime` curto: a agenda muda enquanto o cliente decide.
 */
export function useMonthAvailability(clinicId: string, dates: string[], cart: CartPayload, enabled: boolean) {
  return useQuery({
    queryKey: bookingKeys.availability(clinicId, dates, cart),
    queryFn: () => bookingService.availability(clinicId, dates, cart),
    enabled: enabled && dates.length > 0 && cart.serviceIds.length > 0,
    staleTime: 1000 * 30,
  })
}

/**
 * Total, desconto e valor final. É leitura (useQuery) mesmo sendo POST.
 * `keepPreviousData`: ao entrar o telefone, o valor anterior fica na tela
 * até o novo chegar, em vez de piscar um skeleton.
 */
export function useQuote(clinicId: string, cart: CartPayload, phone: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: bookingKeys.quote(clinicId, cart, phone),
    queryFn: () => bookingService.quote(clinicId, cart, phone),
    enabled: enabled && cart.serviceIds.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 1000 * 60,
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
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateAppointmentPayload) => bookingService.createAppointment(clinicId, payload),
    // O horário marcado deixou de existir — e, num 409, a grade em cache está
    // desatualizada. Nos dois casos a próxima visita à agenda busca de novo.
    onSettled: () => queryClient.invalidateQueries({ queryKey: bookingKeys.availabilityAll(clinicId) }),
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
