import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
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
  const status = useConsentStatus(clinicId, session, consentId)
  const simulate = useSimulateConsent(clinicId, session)
  const consent = status.data ?? created
  const refetch = status.refetch
  const [widget, setWidget] = useState<'loading' | 'ready' | 'failed'>('loading')
  const [height, setHeight] = useState<number | null>(null)
  const [attempt, setAttempt] = useState(0)

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
          () => void refetch(),
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

  return (
    <div className="flex flex-col gap-6">
      <StepHeader title="Assine o termo">
        Leia o termo, digite o código que chegou no seu WhatsApp e assine na tela.
      </StepHeader>

      {consent.test ? (
        <p className="rounded-2xl border border-accent-200 bg-accent-50 px-5 py-3 text-center text-base text-accent-700">
          <strong className="font-bold">TESTE</strong>: este termo não tem valor jurídico.
        </p>
      ) : null}

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
            <p className="flex items-center justify-center gap-3 text-lg text-ink-600">
              <Spinner size="md" className="text-ink-400" />
              Carregando o termo…
            </p>
          ) : null}
          <div
            id={CONTAINER_ID}
            data-testid="clicksign-widget"
            className="w-full overflow-hidden rounded-3xl bg-surface shadow-card"
            style={{ minHeight: '70vh', height: height ? `${height}px` : undefined }}
          />
        </>
      ) : null}

      {!created.canSimulate && !useWidget ? (
        <ErrorMessage>
          O termo não está pronto para assinar. Chame a recepção, por favor.
        </ErrorMessage>
      ) : null}

      <p className="flex items-center justify-center gap-3 text-lg text-ink-600" aria-live="polite">
        <Spinner size="md" className="text-ink-400" />
        Aguardando a assinatura…
      </p>
    </div>
  )
}
