import { parseDate, todayStr } from './dateHelpers'

/**
 * Rótulo de uma data no seletor de agendamento: "Terça, 23 de setembro".
 *
 * O dia da semana vem primeiro porque é assim que se conversa sobre agenda -
 * a clínica combina "terça", não "23/09". O ano só aparece quando a data sai
 * do ano corrente, para não repetir o óbvio em toda linha da lista.
 */
export function formatDateOption(dateStr: string, hoje: string = todayStr()): string {
  const data = parseDate(dateStr)

  // "terça-feira" -> "Terça". O sufixo não acrescenta nada num rótulo curto.
  const diaDaSemana = data
    .toLocaleDateString('pt-BR', { weekday: 'long' })
    .replace('-feira', '')
  const capitalizado = diaDaSemana.charAt(0).toUpperCase() + diaDaSemana.slice(1)

  const mes = data.toLocaleDateString('pt-BR', { month: 'long' })
  const ano = dateStr.slice(0, 4) !== hoje.slice(0, 4) ? ` de ${dateStr.slice(0, 4)}` : ''

  return `${capitalizado}, ${data.getDate()} de ${mes}${ano}`
}
