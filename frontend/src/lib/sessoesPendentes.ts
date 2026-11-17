import type { SessaoSemRegistro } from '@/types'
import { formatCalendarDate, formatClock } from '@/utils/formatDate'

/**
 * Sessões pendentes de registro que já aconteceram (hoje inclusive), da mais
 * próxima de hoje para a mais antiga.
 *
 * Compara o dia inteiro: uma sessão de hoje às 18h entra mesmo que ainda não
 * tenha chegado a hora. A primeira da lista é a pré-selecionada. O backend
 * devolve também os agendamentos futuros confirmados; esses não são registro
 * possível ainda.
 */
export function sessoesPendentesAteHoje(
  sessoes: SessaoSemRegistro[],
  hoje: string,
): SessaoSemRegistro[] {
  return sessoes
    .filter((s) => s.appointment_date <= hoje)
    .sort(
      (a, b) =>
        b.appointment_date.localeCompare(a.appointment_date) ||
        b.start_time.localeCompare(a.start_time),
    )
}

/** "08/11/2026 · 09:00" */
export function rotuloDaSessao(s: SessaoSemRegistro): string {
  return `${formatCalendarDate(s.appointment_date)} · ${formatClock(s.start_time)}`
}
