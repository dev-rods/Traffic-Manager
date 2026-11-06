import { useCallback, useEffect, useReducer } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAnamneseCatalogo, useClinic } from '@/hooks/useCheckin'
import { useIdleReset } from '@/hooks/useIdleReset'
import { StartStep } from '@/steps/StartStep'
import { PhoneStep } from '@/steps/PhoneStep'
import { CodeStep } from '@/steps/CodeStep'
import { AppointmentStep } from '@/steps/AppointmentStep'
import { AnamneseStep } from '@/steps/AnamneseStep'
import { ConsentDataStep } from '@/steps/ConsentDataStep'
import { ConsentSignStep } from '@/steps/ConsentSignStep'
import { ConsentStartStep } from '@/steps/ConsentStartStep'
import { MethodStep } from '@/steps/MethodStep'
import { CpfStep } from '@/steps/CpfStep'
import { PaymentStep } from '@/steps/PaymentStep'
import { DoneStep } from '@/steps/DoneStep'
import type {
  AnamneseRespostas,
  CheckinAppointment,
  Consent,
  ConsentStartPayload,
  Payment,
  PaymentMethod,
  Session,
} from '@/types'
import { formatCurrencyBRL } from '@/utils/format'

type State =
  | { step: 'start' }
  | { step: 'phone' }
  | { step: 'code'; phone: string; devCode: string | null }
  | { step: 'appointment'; session: Session }
  // Confere áreas, preço e horário DEPOIS do termo e da ficha (pedido do
  // André em 06/11/2026): o check-in é gravado aqui, já com tudo assinado.
  | ({ step: 'appointment-confirm' } & Paying)
  | ({ step: 'consent-data' } & Paying)
  // Ficha de anamnese (PRD 038): 4 telas entre os dados e a assinatura, com
  // os dados conferidos guardados para o envelope.
  | ({
      step: 'anamnese'
      tela: number
      respostas: AnamneseRespostas
      dados: ConsentStartPayload
    } & Paying)
  | ({ step: 'consent-start'; dados: ConsentStartPayload } & Paying)
  | ({ step: 'consent-sign'; consent: Consent } & Paying)
  | ({ step: 'method' } & Paying)
  | ({ step: 'cpf'; method: PaymentMethod } & Paying)
  | ({ step: 'payment'; payment: Payment } & Paying)
  | { step: 'done'; firstName: string | null; message: string }

// O que a etapa de pagamento carrega. `cpf` é o que a pessoa digitou nesta
// visita: num telefone compartilhado ele não vai para o cadastro, e trocar de
// forma de pagamento não pode pedir de novo.
interface Paying {
  session: Session
  appointment: CheckinAppointment
  payerCpfKnown: boolean
  cpf: string | null
  // Termo de consentimento (PRD 036) já resolvido nesta visita (assinado,
  // não exigido). Enquanto for falso e o backend exigir, nada de pagamento.
  consentDone: boolean
}

type Action = { type: 'go'; state: State } | { type: 'reset' }

function reducer(_: State, action: Action): State {
  return action.type === 'reset' ? { step: 'start' } : action.state
}

// Sem toque por 90 s, volta ao início. Esperando o pagamento, a paciente está
// no celular dela, sem tocar no iPad: ali o prazo é maior. Na assinatura
// também: o widget da ClickSign é um iframe de outra origem, e os toques nele
// não chegam ao `useIdleReset`.
const IDLE_MS = 90_000
const IDLE_PAYMENT_MS = 5 * 60_000
const LONG_IDLE_STEPS = new Set(['payment', 'anamnese', 'consent-start', 'consent-sign'])

function firstNameOf(appointment: CheckinAppointment): string | null {
  return appointment.fullName?.trim().split(/\s+/)[0] || null
}

/** Para onde vai a paciente depois de escolher o agendamento: termo e ficha
 * primeiro (se exigidos), senão a conferência do agendamento. */
function depoisDeEscolher(paying: Paying): State {
  if (paying.appointment.consentRequired && !paying.consentDone) {
    return { step: 'consent-data', ...paying }
  }
  return { step: 'appointment-confirm', ...paying }
}

/** Para onde vai a paciente depois de confirmar o agendamento ou criar o pagamento. */
function next(paying: Paying, payment: Payment | null): State {
  const { appointment } = paying
  const firstName = firstNameOf(appointment)
  const amount = formatCurrencyBRL(payment?.amountCents ?? appointment.finalPriceCents)
  if (payment?.status === 'PAID') {
    return {
      step: 'done',
      firstName,
      message: 'Seu pagamento está confirmado. É só aguardar ser chamado(a).',
    }
  }
  if (payment?.status === 'AWAITING_CASH') {
    return {
      step: 'done',
      firstName,
      message: `Check-in feito. Pague ${amount} em dinheiro na recepção.`,
    }
  }
  if (payment?.status === 'PENDING') {
    return { step: 'payment', ...paying, payment }
  }
  if (appointment.finalPriceCents == null || appointment.finalPriceCents <= 0) {
    return {
      step: 'done',
      firstName,
      message: 'Check-in feito. O valor desta sessão é combinado na recepção.',
    }
  }
  return { step: 'method', ...paying }
}

function paying(state: Paying): Paying {
  const { session, appointment, payerCpfKnown, cpf, consentDone } = state
  return { session, appointment, payerCpfKnown, cpf, consentDone }
}

export function CheckinPage() {
  const { clinicId = '' } = useParams()
  const clinic = useClinic(clinicId)
  const anamnese = useAnamneseCatalogo(clinicId).data ?? null
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(reducer, { step: 'start' })
  const go = (s: State) => dispatch({ type: 'go', state: s })

  // Cada etapa começa no topo: a ficha e o termo são longos, e a tela
  // seguinte abria onde a anterior tinha parado.
  const tela = state.step === 'anamnese' ? state.tela : 0
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [state.step, tela])

  const reset = useCallback(() => {
    // O que a pessoa anterior viu não fica em cache para a próxima.
    queryClient.removeQueries({ queryKey: ['checkin', 'appointments'] })
    queryClient.removeQueries({ queryKey: ['checkin', 'payment'] })
    queryClient.removeQueries({ queryKey: ['checkin', 'consent'] })
    dispatch({ type: 'reset' })
  }, [queryClient])

  useIdleReset(
    LONG_IDLE_STEPS.has(state.step) ? IDLE_PAYMENT_MS : IDLE_MS,
    reset,
    state.step !== 'start' && state.step !== 'done'
  )

  const clinicName = clinic.data ? clinic.data.display_name || clinic.data.name : ''

  const alreadyPaid = useCallback(
    (appointment: CheckinAppointment) =>
      dispatch({
        type: 'go',
        state: {
          step: 'done',
          firstName: firstNameOf(appointment),
          message: 'Seu pagamento já está confirmado. É só aguardar ser chamado(a).',
        },
      }),
    []
  )

  return (
    <div
      className={`flex flex-col bg-ink-50 ${
        // Assinando o termo, a página não rola: o iframe da ClickSign ocupa o
        // que sobra da tela e rola por dentro (um scroll só, o do termo).
        state.step === 'consent-sign' ? 'h-dvh overflow-hidden' : 'min-h-dvh'
      }`}
    >
      {state.step !== 'start' ? (
        <header className="border-b border-ink-200 bg-surface">
          <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-6 py-3">
            <span className="flex min-w-0 items-center gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-ink-100 shadow-card">
                {clinic.data?.logo_url ? (
                  <img src={clinic.data.logo_url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <span aria-hidden className="font-display text-lg font-semibold text-ink-600">
                    {clinicName.charAt(0).toUpperCase()}
                  </span>
                )}
              </span>
              <span className="truncate font-display text-lg font-semibold text-ink-900">
                {clinicName}
              </span>
            </span>
            {state.step !== 'done' ? (
              <button
                type="button"
                onClick={reset}
                className="inline-flex min-h-12 shrink-0 items-center gap-2 rounded-xl border border-ink-200 bg-surface px-4 font-display text-base font-semibold text-ink-700 transition-colors duration-150 active:bg-ink-100"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-5 w-5"
                  aria-hidden
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 12a9 9 0 1 0 3-6.7" />
                  <path d="M3 4v5h5" />
                </svg>
                Recomeçar
              </button>
            ) : null}
          </div>
        </header>
      ) : null}

      <main
        className={`mx-auto flex w-full flex-1 flex-col px-6 ${
          state.step === 'consent-sign'
            ? 'min-h-0 max-w-6xl justify-start py-4 pb-[max(1rem,env(safe-area-inset-bottom))]'
            : state.step === 'payment'
              ? 'max-w-2xl justify-center py-8 pb-[max(2rem,env(safe-area-inset-bottom))] md:landscape:max-w-4xl'
              : 'max-w-2xl justify-center py-8 pb-[max(2rem,env(safe-area-inset-bottom))]'
        }`}
      >
        {state.step === 'start' ? (
          <StartStep clinic={clinic.data} onStart={() => go({ step: 'phone' })} />
        ) : null}

        {state.step === 'phone' ? (
          <PhoneStep
            clinicId={clinicId}
            onSent={(phone, devCode) => go({ step: 'code', phone, devCode })}
          />
        ) : null}

        {state.step === 'code' ? (
          <CodeStep
            clinicId={clinicId}
            phone={state.phone}
            devCode={state.devCode}
            onVerified={(token) =>
              go({ step: 'appointment', session: { phone: state.phone, token } })
            }
            onChangePhone={() => go({ step: 'phone' })}
          />
        ) : null}

        {state.step === 'appointment' ? (
          <AppointmentStep
            clinicId={clinicId}
            session={state.session}
            onChosen={(appointment) =>
              go(
                depoisDeEscolher({
                  session: state.session,
                  appointment,
                  payerCpfKnown: false,
                  cpf: null,
                  consentDone: false,
                })
              )
            }
            onAlreadyPaid={alreadyPaid}
            onRestart={reset}
          />
        ) : null}

        {state.step === 'appointment-confirm' ? (
          <AppointmentStep
            clinicId={clinicId}
            session={state.session}
            appointment={state.appointment}
            onConfirmed={(appointment, confirmed) =>
              go(
                next(
                  { ...paying(state), appointment, payerCpfKnown: confirmed.payerCpfKnown },
                  appointment.payment
                )
              )
            }
            onAlreadyPaid={alreadyPaid}
            onRestart={reset}
          />
        ) : null}

        {state.step === 'consent-data' ? (
          <ConsentDataStep
            appointment={state.appointment}
            onContinue={(dados) =>
              anamnese
                ? go({
                    ...paying(state),
                    step: 'anamnese',
                    tela: 1,
                    // Sempre em branco: nada pré-assinalado, nem "Não".
                    respostas: {},
                    dados,
                  })
                : go({ ...paying(state), step: 'consent-start', dados })
            }
            onRestart={reset}
          />
        ) : null}

        {state.step === 'anamnese' && anamnese ? (
          <AnamneseStep
            key={state.tela}
            clinicId={clinicId}
            session={state.session}
            appointment={state.appointment}
            catalogo={anamnese}
            tela={state.tela}
            respostas={state.respostas}
            onBack={() =>
              state.tela === 1
                ? go({ ...paying(state), step: 'consent-data' })
                : go({ ...state, tela: state.tela - 1 })
            }
            onNext={(respostas) =>
              state.tela < anamnese.screens.length
                ? go({ ...state, tela: state.tela + 1, respostas })
                : go({ ...paying(state), step: 'consent-start', dados: state.dados })
            }
          />
        ) : null}

        {state.step === 'consent-start' ? (
          <ConsentStartStep
            clinicId={clinicId}
            session={state.session}
            appointmentId={state.appointment.id}
            payload={state.dados}
            onStarted={(consent) =>
              consent.status === 'SIGNING'
                ? go({ ...paying(state), step: 'consent-sign', consent })
                : go({ ...paying(state), step: 'appointment-confirm', consentDone: true })
            }
          />
        ) : null}

        {state.step === 'consent-sign' ? (
          <ConsentSignStep
            clinicId={clinicId}
            session={state.session}
            consent={state.consent}
            onSigned={() =>
              go({ ...paying(state), step: 'appointment-confirm', consentDone: true })
            }
            onRestart={reset}
          />
        ) : null}

        {state.step === 'method' ? (
          <MethodStep
            clinicId={clinicId}
            session={state.session}
            appointment={state.appointment}
            payerCpfKnown={state.payerCpfKnown}
            cpf={state.cpf}
            onNeedCpf={(method) => go({ ...paying(state), step: 'cpf', method })}
            onPayment={(payment) => go(next(paying(state), payment))}
          />
        ) : null}

        {state.step === 'cpf' ? (
          <CpfStep
            clinicId={clinicId}
            session={state.session}
            appointment={state.appointment}
            method={state.method}
            onPayment={(payment, cpf) => go(next({ ...paying(state), cpf }, payment))}
            onBack={() => go({ ...paying(state), step: 'method' })}
          />
        ) : null}

        {state.step === 'payment' ? (
          <PaymentStep
            clinicId={clinicId}
            session={state.session}
            payment={state.payment}
            onPaid={(payment) => go(next(paying(state), payment))}
            onChangeMethod={() => go({ ...paying(state), step: 'method' })}
          />
        ) : null}

        {state.step === 'done' ? (
          <DoneStep firstName={state.firstName} message={state.message} onFinish={reset} />
        ) : null}
      </main>
    </div>
  )
}
