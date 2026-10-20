import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Keypad } from '@/components/ui/Keypad'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { usePay } from '@/hooks/useCheckin'
import type { CheckinAppointment, Payment, PaymentMethod, Session } from '@/types'
import { formatCpf, isValidCpf } from '@/utils/format'

interface CpfStepProps {
  clinicId: string
  session: Session
  appointment: CheckinAppointment
  method: PaymentMethod
  onPayment: (payment: Payment, cpf: string) => void
  onBack: () => void
}

/**
 * Só aparece quando o sistema não sabe o CPF de quem paga: o Asaas não cobra
 * sem ele. Num telefone compartilhado, o CPF do cadastro pode ser de outra
 * pessoa, e o backend pergunta de novo em vez de cobrar no CPF errado.
 */
export function CpfStep({
  clinicId,
  session,
  appointment,
  method,
  onPayment,
  onBack,
}: CpfStepProps) {
  const [digits, setDigits] = useState('')
  const pay = usePay(clinicId, session)
  const complete = digits.length === 11
  const invalid = complete && !isValidCpf(digits)

  function submit() {
    pay.mutate(
      { appointmentId: appointment.id, method, cpf: digits },
      { onSuccess: (payment) => onPayment(payment, digits) }
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Qual é o seu CPF?">Precisamos dele para emitir o pagamento.</StepHeader>
      <output
        aria-label="CPF digitado"
        className="mx-auto min-h-16 w-full max-w-sm rounded-2xl border-2 border-ink-200 bg-surface px-5 py-3 text-center font-display text-3xl font-semibold tabular-nums text-ink-900"
      >
        {digits ? formatCpf(digits) : <span className="text-ink-300">000.000.000-00</span>}
      </output>
      <Keypad
        value={digits}
        maxLength={11}
        onChange={(d) => {
          setDigits(d)
          pay.reset()
        }}
        disabled={pay.isPending}
      />
      {invalid ? <ErrorMessage>Confira o CPF: os números não batem.</ErrorMessage> : null}
      {pay.isError ? <ErrorMessage>{pay.error.message}</ErrorMessage> : null}
      <div className="mx-auto flex w-full max-w-sm flex-col gap-2">
        <Button disabled={!complete || invalid} loading={pay.isPending} onClick={submit}>
          Continuar
        </Button>
        <Button variant="ghost" onClick={onBack} disabled={pay.isPending}>
          Trocar forma de pagamento
        </Button>
      </div>
    </div>
  )
}
