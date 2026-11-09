import type { Appointment } from '@/types'

/**
 * O que muda num agendamento já marcado, em palavras (PRD 043).
 *
 * Fonte única da regra: quais campos têm efeito FORA da tela - e portanto
 * pedem confirmação - e o que se avisa sobre cada um. O modal lê daqui; o
 * teste fixa aqui.
 *
 * Campos sem efeito fora da tela (observação, primeira visita) salvam direto,
 * por decisão do André em 08/11/2026: confirmação que não compra nada treina a
 * clicar sem ler, e é a mesma razão pela qual falta e presença não têm modal.
 */

export interface LinhaDaAlteracao {
  rotulo: string
  de: string
  para: string
}

/** Estado do formulário, já resolvido em texto legível por quem chama. */
export interface AlteracaoPretendida {
  data?: { de: string; para: string }
  horario?: { de: string; para: string }
  servico?: { de: string; para: string }
  areas?: { de: string; para: string }
  desconto?: { de: string; para: string }
  duracao?: { de: string; para: string }
}

export function linhasDaAlteracao(a: AlteracaoPretendida): LinhaDaAlteracao[] {
  const ordem: [keyof AlteracaoPretendida, string][] = [
    ['data', 'Data'],
    ['horario', 'Horário'],
    ['servico', 'Serviço'],
    ['areas', 'Áreas'],
    ['duracao', 'Duração'],
    ['desconto', 'Desconto'],
  ]
  return ordem
    .filter(([chave]) => a[chave])
    .map(([chave, rotulo]) => ({ rotulo, de: a[chave]!.de, para: a[chave]!.para }))
}

/**
 * Os avisos do caso. Cada um existe porque descreve uma consequência que a
 * tela não mostrava: o horário que fica livre, a paciente que não é avisada, a
 * confirmação que se perde, o dinheiro que já entrou.
 */
export function avisosDaAlteracao(
  appointment: Appointment,
  a: AlteracaoPretendida,
): string[] {
  const avisos: string[] = []
  const mudouHorario = Boolean(a.data || a.horario)

  if (mudouHorario) {
    avisos.push('O horário anterior fica livre para outra pessoa.')
    // Nem o painel nem o backend mandam mensagem ao remarcar (conferido nos
    // dois lados em 08/11/2026), e o lembrete do dia antigo é cancelado -
    // então nada chega até ela se ninguém avisar à mão.
    avisos.push('A paciente não será avisada automaticamente desta mudança.')
    if (appointment.confirmado_em) {
      avisos.push(
        'A presença estava confirmada para o horário anterior e voltará a Pendente.',
      )
    }
  }

  if (a.desconto && appointment.payment_status === 'PAID') {
    avisos.push(
      'Este agendamento já foi pago. Mudar o valor não altera o que foi cobrado.',
    )
  }

  return avisos
}

/** Houve mudança com efeito fora da tela? É o que decide pedir confirmação. */
export function temEfeitoForaDaTela(a: AlteracaoPretendida): boolean {
  return linhasDaAlteracao(a).length > 0
}

/** Texto do desconto, para o resumo. */
export function textoDoDesconto(
  modo: 'none' | 'partnership' | 'custom',
  pct: number | string,
): string {
  if (modo === 'partnership') return 'parceria (100%)'
  if (modo === 'custom') {
    const n = Number(pct)
    return Number.isFinite(n) && n > 0 ? `${n}%` : 'sem desconto'
  }
  return 'sem desconto'
}
