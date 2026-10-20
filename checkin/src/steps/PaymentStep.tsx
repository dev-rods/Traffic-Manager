import { useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { QrCode } from '@/components/ui/QrCode'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { usePaymentStatus, useSimulatePayment } from '@/hooks/useCheckin'
import type { Payment, Session } from '@/types'
import { formatCurrencyBRL } from '@/utils/format'

interface PaymentStepProps {
  clinicId: string
  session: Session
  payment: Payment
  onPaid: (payment: Payment) => void
  onChangeMethod: () => void
}

/**
 * Mostra como pagar (Pix ou cartão) e espera. Quem confirma é o provedor
 * (webhook, ou a consulta que o backend faz a cada 3 s); a tela não pergunta
 * "já pagou?". Dinheiro não passa por aqui: a paciente paga na recepção.
 */
export function PaymentStep({
  clinicId,
  session,
  payment: created,
  onPaid,
  onChangeMethod,
}: PaymentStepProps) {
  const status = usePaymentStatus(clinicId, session, created.id)
  const simulate = useSimulatePayment(clinicId, session)
  const payment = status.data ?? created

  useEffect(() => {
    if (payment.status === 'PAID') onPaid(payment)
  }, [payment, onPaid])

  const amount = formatCurrencyBRL(payment.amountCents)

  if (payment.status === 'CANCELLED' || payment.status === 'FAILED') {
    return (
      <div className="flex flex-col gap-6">
        <ErrorMessage>
          Este pagamento foi cancelado. Escolha a forma de pagamento de novo.
        </ErrorMessage>
        <Button onClick={onChangeMethod}>Escolher forma de pagamento</Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-8">
      {payment.method === 'PIX' && payment.pixPayload ? (
        <>
          <StepHeader title={`Pague ${amount} com Pix`}>
            Abra o app do seu banco, escolha Pix e aponte a câmera para o código.
          </StepHeader>
          <QrCode value={payment.pixPayload} label="QR code do Pix" />
        </>
      ) : null}

      {(payment.method === 'CREDIT_CARD' || payment.method === 'DEBIT_CARD') &&
      payment.invoiceUrl ? (
        <>
          <StepHeader title={`Pague ${amount} no seu celular`}>
            Aponte a câmera do celular para o código e pague com cartão de{' '}
            {payment.method === 'CREDIT_CARD' ? 'crédito' : 'débito'}.
          </StepHeader>
          <QrCode value={payment.invoiceUrl} label="QR code da fatura" />
        </>
      ) : null}

      <p className="flex items-center gap-3 text-lg text-ink-600" aria-live="polite">
        <Spinner size="md" className="text-ink-400" />
        Aguardando o pagamento…
      </p>

      {simulate.isError ? <ErrorMessage>{simulate.error.message}</ErrorMessage> : null}

      <div className="flex w-full max-w-sm flex-col gap-2">
        {payment.simulated ? (
          // Só existe com o provedor simulado (dev, sem conta no Asaas).
          <Button
            variant="secondary"
            loading={simulate.isPending}
            onClick={() => simulate.mutate(payment.id, { onSuccess: onPaid })}
          >
            Simular pagamento (teste)
          </Button>
        ) : null}
        <Button variant="ghost" onClick={onChangeMethod}>
          Trocar forma de pagamento
        </Button>
      </div>
    </div>
  )
}
