import { toISODate } from './weekDates'

/**
 * As datas de `today` até o último dia do mês — as que o site pergunta ao
 * backend. Quem decide o que é agendável é o backend (no fuso da clínica; ver
 * `mes_vigente.py`): datas fora da janela voltam CLOSED, e a lista exibida
 * vem da resposta, não daqui. São no máximo 31 datas, o limite por chamada.
 */
export function monthWindow(today: Date): string[] {
  const dates: string[] = []
  const d = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  const month = d.getMonth()
  while (d.getMonth() === month) {
    dates.push(toISODate(d))
    d.setDate(d.getDate() + 1)
  }
  return dates
}
