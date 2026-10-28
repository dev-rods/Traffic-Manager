import type { PaymentMethod, PaymentStatus } from '@/types'

export const METODO_LABEL: Record<PaymentMethod, string> = {
  PIX: 'Pix',
  CREDIT_CARD: 'Crédito',
  DEBIT_CARD: 'Débito',
  CASH: 'Dinheiro',
}

export const METODOS: PaymentMethod[] = ['PIX', 'CREDIT_CARD', 'DEBIT_CARD', 'CASH']

/** Como a recepção lê o estado do pagamento de um agendamento. */
export function situacaoDoPagamento(
  status: PaymentStatus | null | undefined,
  method: PaymentMethod | null | undefined,
): { label: string; tom: 'pago' | 'aguardando' | 'pendente' | 'nada' } {
  const metodo = method ? METODO_LABEL[method] : ''
  if (status === 'PAID') return { label: `Pago · ${metodo}`, tom: 'pago' }
  if (status === 'AWAITING_CASH') return { label: 'Aguardando dinheiro', tom: 'aguardando' }
  if (status === 'PENDING') return { label: `Aguardando ${metodo}`, tom: 'pendente' }
  return { label: 'Não pago', tom: 'nada' }
}

/** `2026-10-19T02:30:00Z` → `18/10`: a data no relógio de quem está na tela, não a de UTC. */
export function dataDe(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

/** `2026-10-19T12:52:00Z` → `09:52`, no relógio de quem está na tela. */
export function horaDe(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}
