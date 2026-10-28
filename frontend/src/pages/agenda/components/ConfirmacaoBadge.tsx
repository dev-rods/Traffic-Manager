import type { Appointment } from '@/types'

/**
 * Pendente ou Confirmado, e so DEPOIS do lembrete (PRD 027).
 *
 * Antes do lembrete nao ha pergunta feita, entao nao ha o que responder: a
 * caixa fica como sempre. Com lembrete enviado, quem respondeu positivamente
 * (bot) ou foi confirmado pela equipe (popover) fica verde; o resto, ambar - e
 * e nessa lista que a recepcao liga na vespera.
 */
export function ConfirmacaoBadge({ appointment: a, compacto = false }: { appointment: Appointment; compacto?: boolean }) {
  if (!a.lembrete_enviado_em || a.status !== 'CONFIRMED') return null
  const confirmado = Boolean(a.confirmado_em)
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
