import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { botService } from '@/services/bot.service'
import { useAuth } from './useAuth'

export const botKeys = {
  all: ['bot'] as const,
  active: (clinicId: string) => [...botKeys.all, 'active', clinicId] as const,
  recent: (clinicId: string) => [...botKeys.all, 'recent', clinicId] as const,
  messages: (clinicId: string, phone: string) => [...botKeys.all, 'messages', clinicId, phone] as const,
  metrics: (clinicId: string, period: string) => [...botKeys.all, 'metrics', clinicId, period] as const,
}

export function useActiveConversations() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: botKeys.active(clinicId!),
    queryFn: () => botService.listActive(clinicId!),
    enabled: !!clinicId,
    refetchInterval: 30 * 1000,
  })
}

export function useRecentConversations(limit = 20) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: botKeys.recent(clinicId!),
    queryFn: () => botService.listRecent(clinicId!, limit),
    enabled: !!clinicId,
    refetchInterval: 30 * 1000,
  })
}

export function useConversationMessages(phone: string | undefined) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: botKeys.messages(clinicId!, phone!),
    queryFn: () => botService.getMessages(clinicId!, phone!),
    enabled: !!clinicId && !!phone,
    refetchInterval: 15 * 1000,
  })
}

export function useBotMetrics(period: 'today' | 'week' | 'month' = 'today') {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: botKeys.metrics(clinicId!, period),
    queryFn: () => botService.getMetrics(clinicId!, period),
    enabled: !!clinicId,
    staleTime: 2 * 60 * 1000,
  })
}

export function usePauseBot() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (phone: string) => botService.pauseForPhone(clinicId!, phone),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: botKeys.active(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.recent(clinicId!) })
    },
  })
}

/**
 * Quando o bot responde algo em aberto, o texto sai numa execução assíncrona que
 * leva de 3 a 15 segundos. Sem recarregar depois, a resposta só apareceria no
 * refetch seguinte e a tela pareceria não ter feito nada. Duas tentativas cobrem
 * o caso típico e o mais lento observado.
 */
const RECARGAS_APOS_RETOMAR_MS = [8000, 16000]

/** Quanto tempo a tela sinaliza que o bot está escrevendo. */
export const ESPERA_RESPOSTA_RETOMADA_MS = RECARGAS_APOS_RETOMAR_MS[RECARGAS_APOS_RETOMAR_MS.length - 1]

export function useResumeBot() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (phone: string) => botService.resumeForPhone(clinicId!, phone),
    onSuccess: (data, phone) => {
      queryClient.invalidateQueries({ queryKey: botKeys.active(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.recent(clinicId!) })

      if (!data.answering_open_question) return
      for (const espera of RECARGAS_APOS_RETOMAR_MS) {
        window.setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: botKeys.messages(clinicId!, phone) })
        }, espera)
      }
    },
  })
}
