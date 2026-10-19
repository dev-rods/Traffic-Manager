import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { caixaService } from '@/services/caixa.service'
import { useAuth } from './useAuth'
import { appointmentKeys } from './useAppointments'

export const caixaKeys = {
  all: ['caixa'] as const,
  resumo: (clinicId: string, dateFrom: string, dateTo: string) =>
    [...caixaKeys.all, 'resumo', clinicId, dateFrom, dateTo] as const,
}

export function useCaixa(dateFrom: string, dateTo: string) {
  const { clinicId } = useAuth()
  return useQuery({
    queryKey: caixaKeys.resumo(clinicId!, dateFrom, dateTo),
    queryFn: () => caixaService.resumo(clinicId!, dateFrom, dateTo),
    enabled: !!clinicId,
    // Pagamento entra pelo iPad a qualquer momento: o caixa aberto na tela
    // não pode ficar parado no que era verdade quando a página carregou.
    refetchInterval: 60_000,
  })
}

/** Baixa em dinheiro. Agenda e caixa mudam juntos: os dois mostram o pagamento. */
export function useReceberDinheiro() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (paymentId: string) => caixaService.receberDinheiro(clinicId!, paymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: caixaKeys.all })
      queryClient.invalidateQueries({ queryKey: appointmentKeys.lists() })
    },
  })
}
