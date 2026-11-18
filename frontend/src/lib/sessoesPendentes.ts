import type { SessaoSemRegistro } from '@/types'
import { formatCalendarDate, formatClock } from '@/utils/formatDate'

/**
 * Sessões pendentes de registro, da data mais recente para a mais antiga.
 *
 * Inclui as futuras: a aplicadora pode registrar uma sessão agendada para os
 * próximos dias (ex.: paciente com um único agendamento confirmado, daqui a
 * dois dias). Filtrá-las aqui fazia o seletor sumir para essa paciente.
 */
export function ordenaPendentes(sessoes: SessaoSemRegistro[]): SessaoSemRegistro[] {
  return [...sessoes].sort(
    (a, b) =>
      b.appointment_date.localeCompare(a.appointment_date) ||
      b.start_time.localeCompare(a.start_time),
  )
}

/**
 * A sessão que já vem escolhida: a mais recente anterior ou igual a hoje.
 *
 * Compara o dia inteiro: uma sessão de hoje às 18h vale mesmo antes das 18h.
 * Recebe a lista já ordenada por `ordenaPendentes`. Sem nenhuma até hoje,
 * devolve `undefined` e o seletor fica em "Registrar manual".
 */
export function sessaoPreSelecionada(
  ordenadas: SessaoSemRegistro[],
  hoje: string,
): SessaoSemRegistro | undefined {
  return ordenadas.find((s) => s.appointment_date <= hoje)
}

/** "08/11/2026 · 09:00" */
export function rotuloDaSessao(s: SessaoSemRegistro): string {
  return `${formatCalendarDate(s.appointment_date)} · ${formatClock(s.start_time)}`
}
