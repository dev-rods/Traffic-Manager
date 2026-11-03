import type { PauseReason } from '@/types'

/**
 * Por que o bot não responde uma conversa, em palavras (PRD 031).
 *
 * Fonte única no front: o cabeçalho da conversa aberta, o selo na lista e o
 * filtro leem daqui. O motivo em si vem do servidor (`atendimento.motivo_da_pausa`).
 */

/** Explicação completa, para o cabeçalho da conversa aberta. */
export const MOTIVO_DA_PAUSA: Record<NonNullable<PauseReason>, string> = {
  attendant: 'Atendimento humano em andamento',
  clinic_paused: 'Bot desligado para toda a clínica',
  not_eligible: 'Fora da regra de resposta automática',
}

/** Rótulo curto, para o selo na lista. */
export const SELO_DA_PAUSA: Record<NonNullable<PauseReason>, string> = {
  attendant: 'Com atendente',
  clinic_paused: 'Bot pausado',
  not_eligible: 'Fora da regra',
}

export const CLASSE_DO_SELO: Record<NonNullable<PauseReason>, string> = {
  attendant: 'bg-blue-50 text-blue-700',
  clinic_paused: 'bg-gray-100 text-gray-600',
  not_eligible: 'bg-amber-50 text-amber-700',
}

export const FILTROS = ['todas', 'fora_da_regra', 'com_atendente', 'bot_ativo'] as const
export type Filtro = (typeof FILTROS)[number]

export const ROTULO_DO_FILTRO: Record<Filtro, string> = {
  todas: 'Todas',
  fora_da_regra: 'Fora da regra',
  com_atendente: 'Com atendente',
  bot_ativo: 'Bot ativo',
}

/**
 * `pause_reason` ausente (backend antigo) conta como "bot ativo": sem motivo,
 * sem selo. É o mesmo que `null`.
 */
export function passaNoFiltro(pauseReason: PauseReason | undefined, filtro: Filtro): boolean {
  switch (filtro) {
    case 'todas':
      return true
    case 'fora_da_regra':
      return pauseReason === 'not_eligible'
    case 'com_atendente':
      return pauseReason === 'attendant'
    case 'bot_ativo':
      return !pauseReason
  }
}
