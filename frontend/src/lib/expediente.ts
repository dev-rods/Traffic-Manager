import { timeToMinutes } from '@/utils/dateHelpers'
import type { Appointment } from '@/types'

/**
 * A janela de agenda que as duas telas desenham.
 *
 * Moram aqui, e não em cada tela, porque a grade do desktop e a lista do
 * celular precisam concordar: se uma mostrasse vão livre às 21h e a outra
 * terminasse às 19h, as duas estariam certas sozinhas e erradas juntas.
 *
 * Não é o horário de funcionamento da clínica - esse vive em
 * `availability_rules`, no banco. É a janela que a agenda desenha, a mesma
 * desde que a grade existe.
 */
export const PRIMEIRA_HORA = 7
export const ULTIMA_HORA = 22

/** Granularidade em que se marca. Vão menor que isto não comporta sessão. */
export const MINUTOS_DO_SLOT = 15

export interface Vao {
  /** Minutos desde a meia-noite. */
  inicio: number
  fim: number
}

/**
 * Os buracos livres de um dia, em ordem.
 *
 * Quem olha a agenda no celular quer saber quando cabe alguém. A lista de
 * atendimentos responde "o que tem marcado"; sem os vãos, descobrir que das
 * 10h às 14h não há nada exige subtrair horários de cabeça, linha a linha.
 *
 * Duas decisões que o caso simples esconde:
 *
 * O cursor anda com o MAIOR fim visto até agora, não com o fim do atendimento
 * anterior. Dois atendimentos simultâneos existem (a grade do desktop tem
 * `distribuiEmColunas` justamente para isso), e um contido dentro do outro -
 * 14h-15h e 14h30-14h45 - abriria um vão fantasma das 14h45 às 15h se o cursor
 * seguisse o último da lista.
 *
 * Atendimento que começa antes da janela, ou termina depois, empurra o cursor
 * do mesmo jeito. O que ele ocupa não está livre só porque cai fora do que a
 * tela desenha.
 */
export function vaosLivres(
  appointments: Appointment[],
  { inicio, fim, minimo = MINUTOS_DO_SLOT }: { inicio: number; fim: number; minimo?: number },
): Vao[] {
  const ocupados = appointments
    .filter((a) => a.status !== 'CANCELLED')
    .map((a) => ({ inicio: timeToMinutes(a.start_time), fim: timeToMinutes(a.end_time) }))
    .sort((a, b) => a.inicio - b.inicio)

  const vaos: Vao[] = []
  let cursor = inicio

  for (const o of ocupados) {
    if (o.inicio - cursor >= minimo) {
      vaos.push({ inicio: cursor, fim: o.inicio })
    }
    cursor = Math.max(cursor, o.fim)
  }

  if (fim - cursor >= minimo) {
    vaos.push({ inicio: cursor, fim })
  }

  return vaos
}

/** "07:00", a partir de minutos desde a meia-noite. */
export function comoHora(minutos: number): string {
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** "1h30", "45 min", "2h" - o tamanho do vão, dito como se fala. */
export function duracaoPorExtenso(minutos: number): string {
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  if (h === 0) return `${m} min`
  if (m === 0) return `${h}h`
  return `${h}h${String(m).padStart(2, '0')}`
}
