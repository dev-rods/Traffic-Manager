import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useStartConsent } from '@/hooks/useCheckin'
import type { Consent, ConsentStartPayload, Session } from '@/types'

interface ConsentStartStepProps {
  clinicId: string
  session: Session
  appointmentId: string
  payload: ConsentStartPayload
  onStarted: (consent: Consent) => void
}

/**
 * Entre a última tela da anamnese e o widget (PRD 038): cria o envelope com
 * os dados confirmados e as respostas já gravadas. Leva alguns segundos, por
 * causa do processamento do documento na ClickSign; a tela diz isso em vez
 * de ficar em branco. Erro tem "Tentar de novo" sem voltar nada.
 */
export function ConsentStartStep({
  clinicId,
  session,
  appointmentId,
  payload,
  onStarted,
}: ConsentStartStepProps) {
  const start = useStartConsent(clinicId, session)
  const mutate = start.mutate
  const disparado = useRef(false)

  useEffect(() => {
    if (disparado.current) return
    disparado.current = true
    mutate({ appointmentId, payload }, { onSuccess: onStarted })
  }, [mutate, appointmentId, payload, onStarted])

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8">
      <StepHeader title="Preparando o documento">
        Estamos montando o termo e a ficha com os seus dados. Leva só alguns segundos.
      </StepHeader>
      {start.isError ? (
        <div className="flex w-full max-w-sm flex-col gap-4">
          <ErrorMessage>{start.error.message}</ErrorMessage>
          <Button
            variant="secondary"
            onClick={() => mutate({ appointmentId, payload }, { onSuccess: onStarted })}
          >
            Tentar de novo
          </Button>
        </div>
      ) : (
        <Spinner size="lg" className="text-ink-400" />
      )}
    </div>
  )
}
