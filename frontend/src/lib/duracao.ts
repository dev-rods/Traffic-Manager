import type { DurationRule } from '@/types'

/**
 * Piso, teto e passo usados quando a clínica ainda não tem regra carregada.
 * Espelham DEFAULT_DURATION_RULES em scheduler/src/services/duration_rules.py.
 */
export const DURACAO_PADRAO = {
  floor_minutes: 15,
  ceiling_minutes: 50,
  step_minutes: 5,
} as const

/** O menor múltiplo de `passo` que não é menor que `minutos`. */
export function arredondaParaPasso(minutos: number, passo: number): number {
  if (passo <= 0) return Math.trunc(minutos)
  return Math.ceil(minutos / passo) * passo
}

/**
 * A duração de uma sessão a partir da soma bruta das áreas.
 *
 * Arredonda para cima: subestimar agenda duas pessoas na mesma janela, e
 * superestimar só desperdiça um vão.
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
