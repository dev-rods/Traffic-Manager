import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useAppointments, useConfirmAppointment } from '@/hooks/useCheckin'
import type { CheckinAppointment, Session } from '@/types'
import { capitalize, formatCurrencyBRL, formatDateLong, isToday } from '@/utils/format'

interface AppointmentStepProps {
  clinicId: string
  session: Session
  onConfirmed: (appointment: CheckinAppointment, payerCpfKnown: boolean) => void
  // Agendamento já pago: não há o que confirmar nem cobrar (PRD 028, M1).
  onAlreadyPaid: (appointment: CheckinAppointment) => void
  onRestart: () => void
}

const METODO: Record<string, string> = {
  PIX: 'Pix',
  CREDIT_CARD: 'Crédito',
  DEBIT_CARD: 'Débito',
  CASH: 'Dinheiro',
  LINK: 'Link',
}

function horaDe(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

/**
 * O estado de um agendamento, para a pessoa não repetir o que já fez. No teste
 * gravado, o agendamento já pago aparecia igual aos outros e pedia
 * "confirmar" de novo, o que pareceu um duplo check-in.
 */
function Situacao({ appointment: a }: { appointment: CheckinAppointment }) {
  if (a.payment?.status === 'PAID') {
    return (
      <span className="rounded-full bg-success-100 px-3 py-1 text-sm font-semibold text-success-600">
        Pago · {METODO[a.payment.method]}
      </span>
    )
  }
  if (a.payment?.status === 'AWAITING_CASH') {
    return (
      <span className="rounded-full bg-accent-100 px-3 py-1 text-sm font-semibold text-accent-700">
        Pagar na recepção
      </span>
    )
  }
  if (a.checkedInAt) {
    return (
      <span className="rounded-full bg-ink-100 px-3 py-1 text-sm font-semibold text-ink-700">
        Check-in às {horaDe(a.checkedInAt)}
      </span>
    )
  }
  return null
}

export function AppointmentStep({
  clinicId,
  session,
  onConfirmed,
  onAlreadyPaid,
  onRestart,
}: AppointmentStepProps) {
  const appointments = useAppointments(clinicId, session)
  const confirm = useConfirmAppointment(clinicId, session)
  const [chosenId, setChosenId] = useState<string | null>(null)

  const list = appointments.data ?? []
  // Um agendamento só: direto para ele. Mais de um (mãe e filha no mesmo
  // número, ou duas sessões marcadas): a pessoa escolhe.
  const chosen = list.length === 1 ? list[0] : list.find((a) => a.id === chosenId)
  const chosenPaid = chosen?.payment?.status === 'PAID' ? chosen : null

  useEffect(() => {
    if (chosenPaid) onAlreadyPaid(chosenPaid)
  }, [chosenPaid, onAlreadyPaid])

  if (appointments.isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center text-ink-500">
        <Spinner size="lg" />
      </div>
    )
  }

  if (appointments.isError) {
    return (
      <div className="flex flex-col gap-6">
        <ErrorMessage>{appointments.error.message}</ErrorMessage>
        <Button variant="secondary" onClick={() => appointments.refetch()}>
          Tentar de novo
        </Button>
      </div>
    )
  }

  if (list.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        <StepHeader title="Não encontramos seu agendamento">
          Este número não tem sessão marcada. Fale com a recepção, por favor.
        </StepHeader>
        <Button variant="secondary" onClick={onRestart} className="w-full max-w-sm">
          Voltar ao início
        </Button>
      </div>
    )
  }

  if (!chosen || chosenPaid) {
    if (chosenPaid) {
      return (
        <div className="flex flex-1 items-center justify-center text-ink-500">
          <Spinner size="lg" />
        </div>
      )
    }
    return (
      <div className="flex flex-col gap-6">
        <StepHeader title="Qual é o seu agendamento?" />
        <div className="flex flex-col gap-3">
          {list.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setChosenId(a.id)}
              className="flex min-h-20 items-center justify-between gap-4 rounded-2xl bg-surface px-6 py-4 text-left shadow-card active:bg-accent-50"
            >
              <span className="flex flex-col gap-1">
                <span className="font-display text-xl font-semibold text-ink-900">
                  {a.fullName ?? 'Agendamento'}
                </span>
                <span className="text-base text-ink-600">
                  {capitalize(formatDateLong(a.date))}, {a.startTime}
                </span>
              </span>
              <span className="ml-auto">
                <Situacao appointment={a} />
              </span>
              <span aria-hidden className="text-2xl text-ink-400">
                ›
              </span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  const firstName = chosen.fullName?.trim().split(/\s+/)[0]

  function handleConfirm() {
    if (!chosen) return
    confirm.mutate(chosen.id, {
      onSuccess: (r) => onConfirmed(chosen, r.payerCpfKnown),
    })
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title={firstName ? `Olá, ${firstName}!` : 'Olá!'}>
        Confira seu agendamento.
      </StepHeader>
      <AppointmentCard appointment={chosen} />
      {chosen.checkedInAt ? (
        <p className="text-center text-base text-ink-600">
          Seu check-in já foi feito às {horaDe(chosen.checkedInAt)}. Falta o pagamento.
        </p>
      ) : null}
      {confirm.isError ? <ErrorMessage>{confirm.error.message}</ErrorMessage> : null}
      <div className="flex flex-col gap-2">
        <Button loading={confirm.isPending} onClick={handleConfirm}>
          {chosen.checkedInAt ? 'Continuar para o pagamento' : 'Está certo, confirmar'}
        </Button>
        {list.length > 1 ? (
          <Button variant="ghost" onClick={() => setChosenId(null)}>
            Escolher outro agendamento
          </Button>
        ) : (
          <p className="text-center text-base text-ink-500">
            Algo errado? Fale com a recepção antes de pagar.
          </p>
        )}
      </div>
    </div>
  )
}

export function AppointmentCard({ appointment }: { appointment: CheckinAppointment }) {
  const today = isToday(appointment.date)
  const hasDiscount =
    appointment.originalPriceCents != null &&
    appointment.finalPriceCents != null &&
    appointment.finalPriceCents < appointment.originalPriceCents

  return (
    <div className="flex flex-col gap-5 rounded-3xl bg-surface p-6 shadow-card">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-display text-2xl font-bold text-ink-900">
          {capitalize(formatDateLong(appointment.date))}
        </p>
        <p className="font-display text-2xl font-bold tabular-nums text-ink-900">
          {appointment.startTime}
        </p>
      </div>
      {!today ? (
        <p className="rounded-xl bg-accent-50 px-4 py-2 text-base font-medium text-accent-700">
          Atenção: este agendamento não é para hoje.
        </p>
      ) : null}
      <div className="flex flex-col gap-1">
        <p className="text-base text-ink-500">{appointment.serviceName ?? 'Sessão'}</p>
        {appointment.areas.length > 0 ? (
          <ul className="flex flex-wrap gap-2" aria-label="Áreas">
            {appointment.areas.map((area) => (
              <li
                key={area}
                className="rounded-full bg-ink-100 px-3 py-1 text-base font-medium text-ink-800"
              >
                {area}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="flex items-end justify-between border-t border-ink-100 pt-4">
        <span className="text-lg text-ink-600">Valor</span>
        {appointment.finalPriceCents != null ? (
          <span className="flex flex-col items-end">
            {hasDiscount ? (
              <span className="text-base tabular-nums text-ink-400 line-through">
                {formatCurrencyBRL(appointment.originalPriceCents)}
              </span>
            ) : null}
            <span className="font-display text-3xl font-bold tabular-nums text-ink-900">
              {formatCurrencyBRL(appointment.finalPriceCents)}
            </span>
          </span>
        ) : (
          <span className="text-lg font-medium text-ink-700">Combinado na recepção</span>
        )}
      </div>
    </div>
  )
}
