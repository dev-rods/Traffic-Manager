import { Button } from '@/components/ui/Button'
import { StepHeader } from '@/components/StepHeader'
import type { CheckinAppointment } from '@/types'
import { capitalize, formatDateLong } from '@/utils/format'

const PASSOS = [
  'Confira seus dados',
  'Responda a ficha de saúde',
  'Assine o termo de consentimento',
]

/**
 * Abertura do fluxo pelo celular (PRD 048): a pessoa já entrou com o código
 * e vê para qual sessão está preenchendo. Três linhas do que vem, um botão.
 */
export function WelcomeStep({
  appointment,
  onStart,
}: {
  appointment: CheckinAppointment
  onStart: () => void
}) {
  const firstName = appointment.fullName?.trim().split(/\s+/)[0] || null
  return (
    <div className="flex flex-col gap-8">
      <StepHeader title={firstName ? `Olá, ${firstName}` : 'Olá'}>
        Sua sessão é {capitalize(formatDateLong(appointment.date))}, às {appointment.startTime}.
        Antes do dia, leva uns 5 minutos:
      </StepHeader>
      <ol className="mx-auto flex w-full max-w-sm flex-col gap-3">
        {PASSOS.map((passo, i) => (
          <li
            key={passo}
            className="flex items-center gap-4 rounded-2xl border-2 border-ink-200 bg-surface px-5 py-4 text-lg text-ink-800"
          >
            <span
              aria-hidden
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-100 font-display text-base font-semibold text-ink-600"
            >
              {i + 1}
            </span>
            {passo}
          </li>
        ))}
      </ol>
      <Button onClick={onStart} className="mx-auto w-full max-w-sm">
        Começar
      </Button>
      <p className="text-center text-base text-ink-500">
        Na hora de assinar, um código chega neste WhatsApp.
      </p>
    </div>
  )
}
