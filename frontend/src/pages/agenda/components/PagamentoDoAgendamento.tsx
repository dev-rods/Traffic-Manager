import { useToast } from '@/components/ui/toastContext'
import { useReceberDinheiro } from '@/hooks/useCaixa'
import { horaDe, situacaoDoPagamento } from '@/utils/pagamento'
import { EnviarLinkDePagamento } from './EnviarLinkDePagamento'
import type { Appointment } from '@/types'

const TOM = {
  pago: 'text-emerald-600',
  aguardando: 'text-amber-600',
  pendente: 'text-amber-600',
  nada: 'text-gray-500',
} as const

interface PagamentoDoAgendamentoProps {
  appointment: Appointment
}

/**
 * Check-in e pagamento feitos no iPad (PRD 026), no detalhe do agendamento.
 *
 * O texto diz o estado, a cor só reforça. "Recebi em dinheiro" aparece só
 * quando a paciente escolheu dinheiro no iPad: é a recepção que recebe a nota
 * e dá a baixa (aqui e no Asaas).
 */
export function PagamentoDoAgendamento({ appointment: a }: PagamentoDoAgendamentoProps) {
  const receber = useReceberDinheiro()
  const { showToast } = useToast()
  // O popover guarda o agendamento de quando foi aberto; depois da baixa, o
  // estado novo vem da própria resposta, sem esperar a agenda recarregar.
  const status = receber.data?.status ?? a.payment_status
  const pagoEm = receber.isSuccess ? new Date().toISOString() : a.payment_paid_at
  const situacao = situacaoDoPagamento(status, a.payment_method)

  function confirmarDinheiro() {
    if (!a.payment_id) return
    receber.mutate(a.payment_id, {
      onSuccess: () => showToast({ message: 'Pagamento em dinheiro registrado' }),
      onError: (erro) =>
        showToast({
          message:
            (erro as { response?: { data?: { message?: string } } })?.response?.data?.message ??
            'Não foi possível registrar o pagamento.',
          variant: 'error',
        }),
    })
  }

  return (
    <div className="px-4 pb-3 space-y-1.5 text-sm">
      <div className="flex justify-between">
        <span className="text-gray-400">Check-in</span>
        <span className="font-medium text-gray-800">
          {a.checked_in_at ? `Feito às ${horaDe(a.checked_in_at)}` : 'Não feito'}
        </span>
      </div>
      <div className="flex justify-between gap-3">
        <span className="text-gray-400">Pagamento</span>
        <span className={`font-medium text-right ${TOM[situacao.tom]}`}>
          {situacao.label}
          {status === 'PAID' && pagoEm ? ` às ${horaDe(pagoEm)}` : ''}
        </span>
      </div>
      {status === 'AWAITING_CASH' && a.payment_id && (
        <button
          type="button"
          onClick={confirmarDinheiro}
          disabled={receber.isPending}
          className="mt-1 w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60 cursor-pointer"
        >
          {receber.isPending ? 'Registrando…' : 'Recebi em dinheiro'}
        </button>
      )}
      {/* Quem não pagou no check-in recebe o link pelo WhatsApp (PRD 029). */}
      {a.status === 'CONFIRMED' &&
        status !== 'PAID' &&
        (!('final_price_cents' in a) || (a.final_price_cents ?? 0) > 0) && (
          <EnviarLinkDePagamento
            appointmentId={a.id}
            linkPendente={a.payment_method === 'LINK' && status === 'PENDING'}
          />
        )}
    </div>
  )
}
