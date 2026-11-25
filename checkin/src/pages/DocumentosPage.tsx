import { useCallback, useEffect, useReducer } from 'react'
import { useParams } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAnamneseCatalogo, useAppointments, useClinic } from '@/hooks/useCheckin'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorMessage } from '@/components/StepHeader'
import { PhoneStep } from '@/steps/PhoneStep'
import { CodeStep } from '@/steps/CodeStep'
import { WelcomeStep } from '@/steps/WelcomeStep'
import { NothingToDoStep } from '@/steps/NothingToDoStep'
import { NotFoundStep } from '@/steps/NotFoundStep'
import { AnamneseStep } from '@/steps/AnamneseStep'
import { ConsentDataStep } from '@/steps/ConsentDataStep'
import { ConsentStartStep } from '@/steps/ConsentStartStep'
import { ConsentSignStep } from '@/steps/ConsentSignStep'
import { DoneStep } from '@/steps/DoneStep'
import { ApiError } from '@/services/api'
import type {
  AnamneseRespostas,
  CheckinAppointment,
  Consent,
  ConsentStartPayload,
  Session,
} from '@/types'

interface Doc {
  session: Session
  appointment: CheckinAppointment
}

type State =
  | { step: 'phone'; aviso: string | null }
  | { step: 'code'; phone: string; devCode: string | null }
  | { step: 'loading'; session: Session }
  | { step: 'nothing'; firstName: string | null }
  | { step: 'not-found' }
  | ({ step: 'welcome' } & Doc)
  | ({ step: 'consent-data' } & Doc)
  | ({
      step: 'anamnese'
      tela: number
      respostas: AnamneseRespostas
      dados: ConsentStartPayload
    } & Doc)
  | ({ step: 'consent-start'; dados: ConsentStartPayload } & Doc)
  | ({ step: 'consent-sign'; consent: Consent } & Doc)
  | { step: 'done'; firstName: string | null }

type Action = { type: 'go'; state: State }

function reducer(_: State, action: Action): State {
  return action.state
}

const SESSAO_VENCIDA = 'Sua sessão venceu. Entre de novo; o que você já respondeu está guardado.'

function firstNameOf(appointment: CheckinAppointment | undefined): string | null {
  return appointment?.fullName?.trim().split(/\s+/)[0] || null
}

function doc(state: Doc): Doc {
  return { session: state.session, appointment: state.appointment }
}

/**
 * Termo e ficha pelo celular, antes da sessão (PRD 048). Mesmos passos de
 * documento do iPad, sem chegada nem pagamento: o token é de escopo
 * `documentos` e o backend recusa `confirm` e `payments` com ele.
 *
 * Diferenças do quiosque: sem reset por inatividade (o celular é da pessoa),
 * teclado do aparelho, e a ficha abre com o que já foi respondido
 * (`anamnesisAnswers`), porque aqui a pessoa pode ter parado no meio.
 */
export function DocumentosPage() {
  const { clinicId = '' } = useParams()
  const clinic = useClinic(clinicId)
  const anamnese = useAnamneseCatalogo(clinicId).data ?? null
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(reducer, { step: 'phone', aviso: null })
  const go = useCallback((s: State) => dispatch({ type: 'go', state: s }), [])

  const tela = state.step === 'anamnese' ? state.tela : 0
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [state.step, tela])

  const entrarDeNovo = useCallback(
    (aviso: string | null) => {
      queryClient.removeQueries({ queryKey: ['checkin', 'appointments'] })
      queryClient.removeQueries({ queryKey: ['checkin', 'consent'] })
      go({ step: 'phone', aviso })
    },
    [queryClient, go]
  )

  // Depois do código: a sessão com documento pendente, "nada a fazer", ou
  // número sem sessão. Lista vazia NUNCA é "tudo certo" (PRD 063): foi o que
  // fez a recepção registrar um termo em papel que não existia.
  const lista = useAppointments(clinicId, state.step === 'loading' ? state.session : null)
  useEffect(() => {
    if (state.step !== 'loading') return
    if (lista.data) {
      const pendente = lista.data.find((a) => a.consentRequired)
      if (lista.data.length === 0) go({ step: 'not-found' })
      else if (pendente) go({ step: 'welcome', session: state.session, appointment: pendente })
      else go({ step: 'nothing', firstName: firstNameOf(lista.data[0]) })
    } else if (lista.error instanceof ApiError && lista.error.status === 401) {
      entrarDeNovo(SESSAO_VENCIDA)
    }
  }, [state, lista.data, lista.error, go, entrarDeNovo])

  const clinicName = clinic.data ? clinic.data.display_name || clinic.data.name : ''
  const comSessao = state.step !== 'phone' && state.step !== 'code' && state.step !== 'done'

  return (
    <div
      className={`flex flex-col bg-ink-50 ${
        state.step === 'consent-sign' ? 'h-dvh overflow-hidden' : 'min-h-dvh'
      }`}
    >
      <header className="border-b border-ink-200 bg-surface">
        <div className="mx-auto flex max-w-md items-center justify-between gap-4 px-4 py-3">
          <span className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-ink-100 shadow-card">
              {clinic.data?.logo_url ? (
                <img src={clinic.data.logo_url} alt="" className="h-full w-full object-cover" />
              ) : (
                <span aria-hidden className="font-display text-base font-semibold text-ink-600">
                  {clinicName.charAt(0).toUpperCase()}
                </span>
              )}
            </span>
            <span className="truncate font-display text-base font-semibold text-ink-900">
              {clinicName}
            </span>
          </span>
          {comSessao && state.step !== 'nothing' && state.step !== 'not-found' ? (
            <button
              type="button"
              onClick={() => entrarDeNovo(null)}
              className="inline-flex min-h-11 shrink-0 items-center rounded-xl border border-ink-200 bg-surface px-3 font-display text-sm font-semibold text-ink-700 transition-colors duration-150 active:bg-ink-100"
            >
              Entrar de novo
            </button>
          ) : null}
        </div>
      </header>

      <main
        className={`mx-auto flex w-full flex-1 flex-col px-4 ${
          state.step === 'consent-sign'
            ? 'min-h-0 max-w-3xl justify-start py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]'
            : 'max-w-md justify-center py-6 pb-[max(1.5rem,env(safe-area-inset-bottom))]'
        }`}
      >
        {state.step === 'phone' ? (
          <div className="flex flex-col gap-6">
            {state.aviso ? <ErrorMessage>{state.aviso}</ErrorMessage> : null}
            <PhoneStep
              clinicId={clinicId}
              teclado="nativo"
              descricao="Digite o WhatsApp em que você recebeu o link. Vamos mandar um código."
              onSent={(phone, devCode) => go({ step: 'code', phone, devCode })}
            />
          </div>
        ) : null}

        {state.step === 'code' ? (
          <CodeStep
            clinicId={clinicId}
            phone={state.phone}
            devCode={state.devCode}
            teclado="nativo"
            scope="documentos"
            onVerified={(token) =>
              go({ step: 'loading', session: { phone: state.phone, token } })
            }
            onChangePhone={() => go({ step: 'phone', aviso: null })}
          />
        ) : null}

        {state.step === 'loading' ? (
          lista.isError && !(lista.error instanceof ApiError && lista.error.status === 401) ? (
            <ErrorMessage>{lista.error.message}</ErrorMessage>
          ) : (
            <div className="flex flex-1 items-center justify-center" aria-busy>
              <Spinner size="lg" />
            </div>
          )
        ) : null}

        {state.step === 'nothing' ? <NothingToDoStep firstName={state.firstName} /> : null}
        {state.step === 'not-found' ? <NotFoundStep onRestart={() => entrarDeNovo(null)} /> : null}

        {state.step === 'welcome' ? (
          <WelcomeStep
            appointment={state.appointment}
            onStart={() => go({ ...doc(state), step: 'consent-data' })}
          />
        ) : null}

        {state.step === 'consent-data' ? (
          <ConsentDataStep
            appointment={state.appointment}
            onContinue={(dados) =>
              anamnese
                ? go({
                    ...doc(state),
                    step: 'anamnese',
                    tela: 1,
                    // Pelo celular, retoma o que já foi respondido.
                    respostas: state.appointment.anamnesisAnswers ?? {},
                    dados,
                  })
                : go({ ...doc(state), step: 'consent-start', dados })
            }
            onRestart={() => entrarDeNovo(null)}
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
                ? go({ ...doc(state), step: 'consent-data' })
                : go({ ...state, tela: state.tela - 1 })
            }
            onNext={(respostas) =>
              state.tela < anamnese.screens.length
                ? go({ ...state, tela: state.tela + 1, respostas })
                : go({ ...doc(state), step: 'consent-start', dados: state.dados })
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
                ? go({ ...doc(state), step: 'consent-sign', consent })
                : go({ step: 'done', firstName: firstNameOf(state.appointment) })
            }
          />
        ) : null}

        {state.step === 'consent-sign' ? (
          <ConsentSignStep
            clinicId={clinicId}
            session={state.session}
            consent={state.consent}
            onSigned={() => go({ step: 'done', firstName: firstNameOf(state.appointment) })}
            onRestart={() => entrarDeNovo(null)}
          />
        ) : null}

        {state.step === 'done' ? (
          <DoneStep
            firstName={state.firstName}
            message="Documento assinado. No dia, é só confirmar e pagar na recepção."
            remoto
            onFinish={() => entrarDeNovo(null)}
          />
        ) : null}
      </main>
    </div>
  )
}
