import type { AvailabilityRule } from '@/types'

/**
 * O desfecho de um agendamento que não acontece como marcado (PRD 054).
 *
 * Cancelar com 24 h ou mais antes da ABERTURA DA AGENDA no dia da sessão é
 * cancelamento; com menos, falta. A decisão é do backend (`desfecho.py`); esta
 * é a mesma conta, só para a tela dizer antes o que vai acontecer. O relógio
 * é o do navegador, que na recepção é o da clínica.
 */

export type Desfecho = 'CANCELLED' | 'NO_SHOW'

export const LIMITE_HORAS = 24

/** "HH:MM" da regra mais cedo do dia; data fixa vence a recorrente; sem regra, a hora da sessão. */
export function aberturaDoDia(
  regras: AvailabilityRule[] | undefined,
  dia: string,
  horaDaSessao: string,
): string {
  const ativas = (regras ?? []).filter((r) => r.active !== false)
  const fixas = ativas.filter((r) => r.rule_date === dia)
  const diaDaSemana = new Date(`${dia}T12:00:00`).getDay()
  const doDia = fixas.length > 0 ? fixas : ativas.filter((r) => r.rule_date == null && r.day_of_week === diaDaSemana)
  if (doDia.length === 0) return horaDaSessao.slice(0, 5)
  return doDia.map((r) => r.start_time.slice(0, 5)).sort()[0]
}

export function desfechoAutomatico(agora: Date, dia: string, abertura: string): Desfecho {
  const limite = new Date(`${dia}T${abertura.slice(0, 5)}:00`)
  limite.setHours(limite.getHours() - LIMITE_HORAS)
  return agora.getTime() <= limite.getTime() ? 'CANCELLED' : 'NO_SHOW'
}

/** O desfecho que o backend dará a este agendamento se for cancelado agora. */
export function desfechoDe(
  regras: AvailabilityRule[] | undefined,
  a: { appointment_date: string; start_time: string },
  agora: Date = new Date(),
): Desfecho {
  return desfechoAutomatico(agora, a.appointment_date, aberturaDoDia(regras, a.appointment_date, a.start_time))
}

export function nomeDoDesfecho(d: Desfecho): string {
  return d === 'NO_SHOW' ? 'falta' : 'cancelamento'
}

/** A frase do modal: o que vai acontecer e por quê. */
export function explicaDesfecho(d: Desfecho): string {
  return d === 'NO_SHOW'
    ? `Vai contar como falta: faltam menos de ${LIMITE_HORAS} h para a abertura da agenda do dia.`
    : `Vai contar como cancelamento: ainda faltam ${LIMITE_HORAS} h ou mais para a abertura da agenda do dia.`
}
