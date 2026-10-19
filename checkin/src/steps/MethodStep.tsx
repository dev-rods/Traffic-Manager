import type { ReactNode } from 'react'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { Spinner } from '@/components/ui/Spinner'
import { usePay } from '@/hooks/useCheckin'
import type { CheckinAppointment, Payment, PaymentMethod, Session } from '@/types'
import { formatCurrencyBRL } from '@/utils/format'

const METHOD_LABEL: Record<PaymentMethod, string> = {
  PIX: 'Pix',
  CREDIT_CARD: 'Crédito',
  DEBIT_CARD: 'Débito',
  CASH: 'Dinheiro',
}

const METHOD_HINT: Record<PaymentMethod, string> = {
  PIX: 'QR code no seu celular',
  CREDIT_CARD: 'Pague pelo seu celular',
  DEBIT_CARD: 'Pague pelo seu celular',
  CASH: 'Pague na recepção',
}

const ORDER: PaymentMethod[] = ['PIX', 'CREDIT_CARD', 'DEBIT_CARD', 'CASH']

interface MethodStepProps {
  clinicId: string
  session: Session
  appointment: CheckinAppointment
  payerCpfKnown: boolean
  // CPF digitado nesta visita (telefone compartilhado: não está no cadastro).
  cpf: string | null
  onNeedCpf: (method: PaymentMethod) => void
  onPayment: (payment: Payment) => void
}

export function MethodStep({
  clinicId,
  session,
  appointment,
  payerCpfKnown,
  cpf,
  onNeedCpf,
  onPayment,
}: MethodStepProps) {
  const pay = usePay(clinicId, session)

  function choose(method: PaymentMethod) {
    if (!payerCpfKnown && !cpf) {
      onNeedCpf(method)
      return
    }
    pay.mutate(
      { appointmentId: appointment.id, method, cpf: cpf ?? undefined },
      { onSuccess: onPayment }
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Como você quer pagar?">
        Valor da sessão:{' '}
        <strong className="font-semibold text-ink-900">
          {formatCurrencyBRL(appointment.finalPriceCents)}
        </strong>
      </StepHeader>
      <div className="grid grid-cols-2 gap-4">
        {ORDER.map((method) => (
          <MethodTile
            key={method}
            disabled={pay.isPending}
            loading={pay.isPending && pay.variables?.method === method}
            onClick={() => choose(method)}
            hint={METHOD_HINT[method]}
          >
            {METHOD_LABEL[method]}
          </MethodTile>
        ))}
      </div>
      {pay.isError ? <ErrorMessage>{pay.error.message}</ErrorMessage> : null}
    </div>
  )
}

function MethodTile({
  children,
  hint,
  onClick,
  disabled,
  loading,
}: {
  children: ReactNode
  hint: string
  onClick: () => void
  disabled: boolean
  loading: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex min-h-36 flex-col items-center justify-center gap-2 rounded-3xl bg-surface p-5 text-center shadow-card transition-colors duration-150 active:bg-accent-50 disabled:opacity-50"
    >
      {loading ? (
        <Spinner size="lg" className="text-ink-400" />
      ) : (
        <>
          <span className="font-display text-3xl font-bold text-ink-900">{children}</span>
          <span className="text-base text-ink-500">{hint}</span>
        </>
      )}
    </button>
  )
}
