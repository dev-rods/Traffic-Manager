import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { botService } from '@/services/bot.service'
import { useAuth } from './useAuth'

export const botKeys = {
  all: ['bot'] as const,
  active: (clinicId: string) => [...botKeys.all, 'active', clinicId] as const,
  recent: (clinicId: string) => [...botKeys.all, 'recent', clinicId] as const,
  messages: (clinicId: string, phone: string) => [...botKeys.all, 'messages', clinicId, phone] as const,
  metrics: (clinicId: string, period: string) => [...botKeys.all, 'metrics', clinicId, period] as const,
  tarefas: (clinicId: string) => [...botKeys.all, 'tarefas', clinicId] as const,
  status: (clinicId: string, phone: string) => [...botKeys.all, 'status', clinicId, phone] as const,
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

/**
 * Fechar a tarefa e o que tira a conversa de HUMAN_PENDING: ela vai para o
 * cooldown (o bot responde se a paciente escrever, mas nao inicia nada). A fila
 * e recarregada porque a linha muda de aba.
 */
export function useFecharTarefa() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (tarefaId: string) => botService.fecharTarefa(clinicId!, tarefaId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: botKeys.active(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.tarefas(clinicId!) })
    },
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

/**
 * Quem silenciou este contato, quando e por quê (PRD 039). Só é consultado
 * quando a conversa está aberta: o selo na lista já sai de `pause_reason`, e
 * o motivo escrito só faz falta no cabeçalho.
 */
export function useSilencioDoContato(phone: string | null) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: botKeys.status(clinicId!, phone ?? ''),
    queryFn: () => botService.getPhoneStatus(clinicId!, phone!),
    enabled: !!clinicId && !!phone,
    select: (data) => data.silencio,
  })
}

/**
 * Silenciar e reativar o contato (PRD 039). Invalida as mesmas listas da
 * pausa de 24h, porque é o mesmo selo que muda na tela.
 */
export function useSilenciarContato() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ phone, motivo }: { phone: string; motivo: string }) =>
      botService.silenciar(clinicId!, phone, motivo),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: botKeys.active(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.recent(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.all })
    },
  })
}

export function useReativarSilencio() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (phone: string) => botService.reativarSilencio(clinicId!, phone),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: botKeys.active(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.recent(clinicId!) })
      queryClient.invalidateQueries({ queryKey: botKeys.all })
    },
  })
}

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
