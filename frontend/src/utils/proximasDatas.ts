import { todayStr } from './dateHelpers'

interface RegraComData {
  rule_date: string | null
}

/**
 * As proximas datas com regra de atendimento, limitadas por `max_future_dates`
 * da clinica: e o que o disparo em lote oferece como "datas abertas".
 *
 * Extraido de PacientesPage para a fila do CRM (PRD 057) oferecer as mesmas
 * datas que a tela de pacientes, sem duas copias que divergem em silencio.
 */
export function proximasDatas(regras: RegraComData[] | undefined, maxFutureDates: number | null | undefined): string[] {
  const hoje = todayStr()
  const teto = maxFutureDates ?? 5
  return (regras ?? [])
    .map((r) => r.rule_date)
    .filter((d): d is string => d !== null && d >= hoje)
    .sort()
    .slice(0, teto)
}
