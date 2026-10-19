import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Keypad } from '@/components/ui/Keypad'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useSendCode } from '@/hooks/useCheckin'
import { formatPhone, isValidMobile, toApiPhone } from '@/utils/format'

export function PhoneStep({
  clinicId,
  onSent,
}: {
  clinicId: string
  onSent: (apiPhone: string) => void
}) {
  const [digits, setDigits] = useState('')
  const sendCode = useSendCode(clinicId)
  const valid = isValidMobile(digits)

  function submit() {
    const phone = toApiPhone(digits)
    sendCode.mutate(phone, { onSuccess: () => onSent(phone) })
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Qual é o seu celular?">Vamos mandar um código no seu WhatsApp.</StepHeader>
      <output
        aria-label="Celular digitado"
        className="mx-auto min-h-16 w-full max-w-sm rounded-2xl border-2 border-ink-200 bg-surface px-5 py-3 text-center font-display text-3xl font-semibold tabular-nums text-ink-900"
      >
        {digits ? formatPhone(digits) : <span className="text-ink-300">(00) 00000-0000</span>}
      </output>
      <Keypad value={digits} maxLength={11} onChange={setDigits} disabled={sendCode.isPending} />
      {sendCode.isError ? <ErrorMessage>{sendCode.error.message}</ErrorMessage> : null}
      <Button
        disabled={!valid}
        loading={sendCode.isPending}
        onClick={submit}
        className="mx-auto w-full max-w-sm"
      >
        Receber código
      </Button>
    </div>
  )
}
