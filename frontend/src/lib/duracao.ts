import type { DurationRule } from '@/types'

/**
 * Piso, teto e passo usados quando a clínica ainda não tem regra carregada.
 * Espelham DEFAULT_DURATION_RULES em scheduler/src/services/duration_rules.py.
 */
export const DURACAO_PADRAO = {
  // 10 desde 11/09/2026 (era 15). Espelha DEFAULT_DURATION_RULES do
  // backend - se divergir, a tela promete um horario de fim que o
  // servidor nao aceita, e quem descobre e o paciente.
  floor_minutes: 10,
  ceiling_minutes: 50,
  step_minutes: 5,
} as const

/**
 * O múltiplo de `passo` mais próximo de `minutos`.
 *
 * Era para cima, e arredondava sempre contra a agenda: 17 minutos viravam 20 e
 * a clínica perdia 3 minutos de sala. Empate vai para cima - só acontece com
 * passo par, e sobrar sala é melhor que a próxima paciente esperar.
 *
 * Espelha `arredonda_para_passo` em scheduler/src/services/duration_rules.py.
 * As duas precisam concordar: divergindo, a tela promete um horário de fim e o
 * banco grava outro.
 */
export function arredondaParaPasso(minutos: number, passo: number): number {
  if (passo <= 0) return Math.trunc(minutos)
  return Math.floor((Math.trunc(minutos) + Math.floor(passo / 2)) / passo) * passo
}

/**
 * A duração de uma sessão a partir da soma bruta das áreas.
 *
 * Arredonda para o múltiplo mais próximo.
 *
 * Isto é PREVIEW. Quem decide é o backend, que reaplica a mesma regra em
 * duracao_da_sessao antes de gravar ou de devolver horários - se os dois
 * divergirem, o servidor vence e a tela é que está errada.
 */
export function calculaDuracao(
  somaMinutos: number,
  regras?: Pick<DurationRule, 'floor_minutes' | 'ceiling_minutes' | 'step_minutes'> | null,
): number {
  const piso = regras?.floor_minutes ?? DURACAO_PADRAO.floor_minutes
  const teto = Math.max(regras?.ceiling_minutes ?? DURACAO_PADRAO.ceiling_minutes, piso)
  const passo = regras?.step_minutes ?? DURACAO_PADRAO.step_minutes

  const bruto = Math.max(somaMinutos || 0, 0)
  return Math.max(piso, Math.min(teto, arredondaParaPasso(bruto, passo)))
}
