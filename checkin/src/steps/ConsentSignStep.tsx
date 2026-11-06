import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorMessage } from '@/components/StepHeader'
import { useConsentStatus, useSimulateConsent } from '@/hooks/useCheckin'
import { loadClicksign, mountClicksign } from '@/lib/clicksignWidget'
import type { Consent, Session } from '@/types'

interface ConsentSignStepProps {
  clinicId: string
  session: Session
  consent: Consent
  onSigned: (consent: Consent) => void
  onRestart: () => void
}

const CONTAINER_ID = 'clicksign-widget'

/**
 * Segunda tela do termo (PRD 036): o widget embedded da ClickSign, onde a
 * paciente lê, recebe o código no WhatsApp e assina na tela. Quem confirma a
 * assinatura é o backend (webhook ou consulta a cada 3 s); o evento `signed`
 * do widget só apressa a consulta. No simulado (dev sem chave) não há widget,
 * só o botão de simular.
 */
export function ConsentSignStep({
  clinicId,
  session,
  consent: created,
  onSigned,
  onRestart,
}: ConsentSignStepProps) {
  const consentId = created.id ?? ''
  const [assinou, setAssinou] = useState(false)
  const status = useConsentStatus(clinicId, session, consentId, assinou)
  const simulate = useSimulateConsent(clinicId, session)
  const consent = status.data ?? created
  const refetch = status.refetch
  const [widget, setWidget] = useState<'loading' | 'ready' | 'failed'>('loading')
  const [height, setHeight] = useState<number | null>(null)
  const [attempt, setAttempt] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)

  useEffect(() => {
    if (consent.status === 'SIGNED') onSigned(consent)
  }, [consent, onSigned])

  const useWidget = !created.canSimulate && Boolean(created.signerId && created.widgetEndpoint)

  useEffect(() => {
    if (!useWidget || !created.signerId) return
    let unmount: (() => void) | null = null
    let cancelled = false
    loadClicksign()
      .then(() => {
        if (cancelled) return
        unmount = mountClicksign(
          created.signerId as string,
          created.widgetEndpoint,
          CONTAINER_ID,
          () => {
            setAssinou(true)
            void refetch()
          },
          (h) => setHeight(h)
        )
        setWidget('ready')
      })
      .catch(() => {
        if (!cancelled) setWidget('failed')
      })
    return () => {
      cancelled = true
      unmount?.()
    }
  }, [useWidget, created.signerId, created.widgetEndpoint, refetch, attempt])

  if (consent.status === 'CANCELLED' || consent.status === 'EXPIRED') {
    return (
      <div className="flex flex-col gap-6">
        <ErrorMessage>Este termo não pôde ser assinado. Chame a recepção, por favor.</ErrorMessage>
        <Button variant="secondary" onClick={onRestart}>
          Voltar ao início
        </Button>
      </div>
    )
  }

  const toggle = (
    <button
      type="button"
      onClick={() => setFullscreen((f) => !f)}
      aria-pressed={fullscreen}
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
        {fullscreen ? (
          <path d="M8 3v5H3M16 3v5h5M8 21v-5H3M16 21v-5h5" />
        ) : (
          <path d="M3 8V3h5M21 8V3h-5M3 16v5h5M21 16v5h-5" />
        )}
      </svg>
      {fullscreen ? 'Reduzir' : 'Tela cheia'}
    </button>
  )

  // A tela toda é do termo: a página não rola (CheckinPage trava a altura
  // neste passo), o cabeçalho é uma linha e o iframe da ClickSign preenche o
  // resto. O PDF precisa de largura e altura de verdade para ser legível no
  // iPad deitado: a ClickSign ainda gasta ~160px de barras próprias por dentro.
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-bold text-ink-900">Assine o termo</h1>
          <p className="text-base text-ink-600" aria-live="polite">
            {assinou
              ? 'Assinatura recebida. Estamos registrando o documento…'
              : useWidget && widget === 'ready'
                ? 'Leia, digite o código do WhatsApp e assine na tela. Aguardando a assinatura…'
                : 'Leia o termo, digite o código que chegou no seu WhatsApp e assine na tela.'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {consent.test ? (
            <span className="rounded-full border border-accent-200 bg-accent-50 px-4 py-2 text-sm font-semibold text-accent-700">
              TESTE: sem valor jurídico
            </span>
          ) : null}
          {useWidget && widget === 'ready' && !fullscreen ? toggle : null}
        </div>
      </div>

      {created.canSimulate ? (
        <div className="flex flex-col items-center gap-4 rounded-3xl bg-surface p-6 shadow-card">
          <p className="text-center text-lg text-ink-600">
            Ambiente de teste sem ClickSign: não há widget. Simule a assinatura para seguir.
          </p>
          {simulate.isError ? <ErrorMessage>{simulate.error.message}</ErrorMessage> : null}
          <Button
            variant="secondary"
            loading={simulate.isPending}
            onClick={() => simulate.mutate(consentId, { onSuccess: onSigned })}
            className="w-full max-w-sm"
          >
            Simular assinatura (teste)
          </Button>
        </div>
      ) : null}

      {useWidget ? (
        <>
          {widget === 'failed' ? (
            <div className="flex flex-col gap-4">
              <ErrorMessage>
                Não conseguimos carregar o termo. Tente de novo ou chame a recepção.
              </ErrorMessage>
              <Button
                variant="secondary"
                onClick={() => {
                  setWidget('loading')
                  setAttempt((n) => n + 1)
                }}
              >
                Tentar de novo
              </Button>
            </div>
          ) : null}
          {widget === 'loading' ? (
            <p className="flex items-center justify-center gap-3 py-4 text-lg text-ink-600">
              <Spinner size="md" className="text-ink-400" />
              Carregando o termo…
            </p>
          ) : null}
          {/* O iframe da ClickSign vem com height: 100%: o container precisa
              de altura definida. Aqui ele é item flex de um pai com altura
              definida (a página em h-dvh, ou o overlay fixed inset-0), que o
              navegador trata como definida. Tela cheia troca só a classe do
              wrapper: o container é o mesmo nó e o iframe não remonta. */}
          <div
            data-testid="clicksign-frame"
            className={
              fullscreen
                ? 'fixed inset-0 z-50 flex flex-col bg-surface pt-[env(safe-area-inset-top)]'
                : 'flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl bg-surface shadow-card'
            }
          >
            {fullscreen ? (
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-ink-200 px-4">
                <span className="font-display text-base font-semibold text-ink-700">
                  Termo de consentimento
                </span>
                {toggle}
              </div>
            ) : null}
            {assinou ? (
              <div
                role="status"
                aria-live="polite"
                className="flex items-center justify-center gap-4 border-b border-success-100 bg-success-100 px-6 py-5 text-lg text-success-600"
              >
                <Spinner size="md" className="text-success-500" />
                <span>
                  <strong className="font-bold">Assinatura recebida!</strong> Aguarde alguns
                  segundos: estamos registrando o documento e já levamos você para conferir o
                  agendamento e pagar.
                </span>
              </div>
            ) : null}
            <div
              id={CONTAINER_ID}
              data-testid="clicksign-widget"
              className="min-h-0 w-full flex-1"
              style={height && !fullscreen ? { height: `${height}px` } : undefined}
            />
          </div>
        </>
      ) : null}

      {!created.canSimulate && !useWidget ? (
        <ErrorMessage>
          O termo não está pronto para assinar. Chame a recepção, por favor.
        </ErrorMessage>
      ) : null}
    </div>
  )
}
