import type { Appointment } from '@/types'

/**
 * Pendente ou Confirmado (PRD 027).
 *
 * "Pendente" so DEPOIS do lembrete: antes nao ha pergunta feita, entao nao ha
 * o que responder, e a caixa fica como sempre. Com lembrete enviado, quem
 * respondeu positivamente (bot) ou foi confirmado pela equipe (popover) fica
 * verde; o resto, ambar - e e nessa lista que a recepcao liga na vespera.
 *
 * "Confirmado" aparece sempre: a equipe confirma por telefone antes de o
 * lembrete sair, e essa confirmacao precisa ficar visivel na agenda.
 */
export function ConfirmacaoBadge({ appointment: a, compacto = false }: { appointment: Appointment; compacto?: boolean }) {
  if (a.status !== 'CONFIRMED') return null
  const confirmado = Boolean(a.confirmado_em)
  if (!confirmado && !a.lembrete_enviado_em) return null
  const cor = confirmado ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
  const titulo = confirmado
    ? `Presença confirmada${a.confirmado_por === 'EQUIPE' ? ' pela equipe' : ' pela paciente'}`
    : 'Lembrete enviado, sem resposta'
  return (
    <span
      title={titulo}
      className={[
        'inline-block rounded px-1 font-bold align-middle',
        compacto ? 'text-[10px] mr-0.5' : 'px-1.5 py-0.5 text-[10px]',
        cor,
      ].join(' ')}
    >
      {confirmado ? 'CONFIRMADO' : 'PENDENTE'}
    </span>
  )
}
