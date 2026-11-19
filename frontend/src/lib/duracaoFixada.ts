/**
 * Faixa de sanidade da duração manual.
 *
 * Espelha MINIMO/MAXIMO em scheduler/src/services/duracao_manual.py. Quem
 * decide é o backend; isto aqui é para a atendente descobrir o erro digitando,
 * não depois de salvar.
 */
export const DURACAO_MANUAL = { minimo: 5, maximo: 480 } as const

/**
 * O número por trás do texto fixado: inteiro dentro da faixa, ou null.
 * `null` de entrada é "seguindo o cálculo" e também sai null (PRD 050).
 */
export function parseDuracao(texto: string | null): number | null {
  if (texto === null) return null
  const limpo = texto.trim()
  if (!/^\d+$/.test(limpo)) return null
  const n = Number(limpo)
  return n >= DURACAO_MANUAL.minimo && n <= DURACAO_MANUAL.maximo ? n : null
}
