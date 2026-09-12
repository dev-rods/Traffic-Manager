import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { leadsService, type LeadListParams } from '@/services/leads.service'
import { useAuth } from './useAuth'

export const leadKeys = {
  all: ['leads'] as const,
  list: (clinicId: string, filters: LeadListParams) => [...leadKeys.all, clinicId, filters] as const,
}

export function useLeads(params?: LeadListParams) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: leadKeys.list(clinicId!, params ?? {}),
    queryFn: () => leadsService.list(clinicId!, params),
    enabled: !!clinicId,
    staleTime: 2 * 60 * 1000,
  })
}

/**
 * Dispara o bot ou alterna o "Ja iniciada".
 *
 * Sem update otimista de proposito: a elegibilidade e recalculada no servidor
 * (seis condicoes, incluindo se outra atendente marcou no meio tempo), entao
 * adivinhar o proximo estado aqui mostraria um botao que o servidor recusa.
 * Invalida e espera a verdade.
 */
export function useAcoesDoLead() {
  const queryClient = useQueryClient()
  const invalida = () => queryClient.invalidateQueries({ queryKey: leadKeys.all })

  const iniciarPeloBot = useMutation({
    mutationFn: (leadId: string) => leadsService.iniciarPeloBot(leadId),
    onSuccess: invalida,
  })

  const alternarContatoManual = useMutation({
    mutationFn: (leadId: string) => leadsService.alternarContatoManual(leadId),
    onSuccess: invalida,
  })

  return { iniciarPeloBot, alternarContatoManual }
}
