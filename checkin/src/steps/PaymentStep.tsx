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
 *
 * Em tela deitada e larga (iPad em paisagem), QR à esquerda e instruções à
 * direita: em uma coluna só, o título saía da tela e o "Trocar forma de
 * pagamento" ficava abaixo da dobra (teste gravado de 28/10/2026, PRD 028 M6).
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

  const pix = payment.method === 'PIX' && payment.pixPayload
  const card =
    (payment.method === 'CREDIT_CARD' || payment.method === 'DEBIT_CARD') && payment.invoiceUrl
  const qrValue = pix ? payment.pixPayload : card ? payment.invoiceUrl : null

  return (
    <div className="flex flex-col items-center gap-6 md:landscape:grid md:landscape:grid-cols-[auto_1fr] md:landscape:items-center md:landscape:gap-12">
      {qrValue ? (
        <div className="md:landscape:order-first">
          <QrCode value={qrValue} label={pix ? 'QR code do Pix' : 'QR code da fatura'} />
        </div>
      ) : null}

      {/* Em pé, a coluna some (contents): título → QR → status → botões. */}
      <div className="contents md:landscape:flex md:landscape:w-full md:landscape:flex-col md:landscape:items-start md:landscape:gap-6">
        <div className="order-first w-full md:landscape:order-none">
          {pix ? (
            <StepHeader title={`Pague ${amount} com Pix`} align="responsive">
              Abra o app do seu banco, escolha Pix e aponte a câmera para o código.
            </StepHeader>
          ) : null}
          {card ? (
            <StepHeader title={`Pague ${amount} no seu celular`} align="responsive">
              Aponte a câmera do celular para o código e pague com cartão de{' '}
              {payment.method === 'CREDIT_CARD' ? 'crédito' : 'débito'}.
            </StepHeader>
          ) : null}
        </div>

        {card && payment.simulated && !payment.canSimulate ? <TestCardHint /> : null}

        <p className="flex items-center gap-3 text-lg text-ink-600" aria-live="polite">
          <Spinner size="md" className="text-ink-400" />
          Aguardando o pagamento…
        </p>

        {simulate.isError ? <ErrorMessage>{simulate.error.message}</ErrorMessage> : null}

        <div className="flex w-full max-w-sm flex-col gap-2">
          {payment.canSimulate ? (
            // Só em teste: provedor simulado, ou Asaas sandbox no Pix.
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
    </div>
  )
}

/**
 * Ambiente de teste (Asaas sandbox): tudo o que a fatura pede. Só o número do
 * cartão não bastava; no teste gravado ninguém sabia o que pôr como titular
 * (PRD 028, M5). Dados do cartão aprovado da documentação do Asaas.
 */
function TestCardHint() {
  return (
    <div className="w-full max-w-md rounded-2xl border border-accent-200 bg-accent-50 px-5 py-4 text-base text-accent-700">
      <p className="font-semibold">Ambiente de teste: dados para a fatura</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt>Cartão</dt>
        <dd className="font-semibold tabular-nums">4444 4444 4444 4444</dd>
        <dt>Validade</dt>
        <dd>qualquer data futura (ex.: 12/2030)</dd>
        <dt>CVV</dt>
        <dd className="tabular-nums">123</dd>
        <dt>Titular</dt>
        <dd>qualquer nome</dd>
        <dt>CPF</dt>
        <dd className="tabular-nums">529.982.247-25</dd>
        <dt>E-mail, CEP, telefone</dt>
        <dd>quaisquer válidos</dd>
      </dl>
    </div>
  )
}
