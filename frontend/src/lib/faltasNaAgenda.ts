import type { Appointment } from '@/types'

/**
 * Falta sai da agenda por padrão, como o cancelado.
 *
 * Decisão do André em 04/10/2026, e o motivo é de espaço: quando o horário é
 * reaproveitado - e ele é, porque as queries de conflito e de horários livres
 * usam `= 'CONFIRMED'`, então `NO_SHOW` libera o slot -, os dois agendamentos
 * se sobrepõem e `distribuiEmColunas` dá metade da largura a cada um. O
 * agendamento que importa encolhe por causa de um registro histórico.
 *
 * Mas não desaparece em silêncio: ver [contaFaltas]. Não existe nenhuma outra
 * tela onde um agendamento em falta seja alcançável - não há histórico de
 * agendamentos do paciente -, então filtrar sem dizer nada esconderia a
 * informação e tiraria o único caminho para "Desmarcar falta" depois que o
 * toast passa.
 *
 * Mora em `lib/` e não dentro da página porque é a regra que decide o que a
 * agenda mostra, e regra que decide merece teste próprio.
 */
export function semFaltas(appointments: Appointment[]): Appointment[] {
  return appointments.filter((a) => a.status !== 'NO_SHOW')
}

/**
 * Quantas faltas existem na faixa visível.
 *
 * É o número que justifica a linha "N faltas ocultas · mostrar". Sem ele, o
 * filtro de [semFaltas] seria uma omissão silenciosa; com ele, a ausência é
 * declarada e reversível.
 *
 * Quando é zero, a linha não aparece: controle permanente para algo que quase
 * sempre está ausente é ruído.
 */
export function contaFaltas(appointments: Appointment[]): number {
  return appointments.filter((a) => a.status === 'NO_SHOW').length
}
