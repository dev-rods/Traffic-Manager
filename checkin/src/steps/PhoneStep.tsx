import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Keypad } from '@/components/ui/Keypad'
import { TextField } from '@/components/ui/TextField'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useSendCode } from '@/hooks/useCheckin'
import { formatPhone, formatPhoneInput, isValidMobile, isValidPhoneInput, onlyDigits, toApiPhone } from '@/utils/format'

export type Teclado = 'keypad' | 'nativo'

export function PhoneStep({
  clinicId,
  onSent,
  teclado = 'keypad',
  descricao = 'Vamos mandar um código no seu WhatsApp.',
}: {
  clinicId: string
  onSent: (apiPhone: string, devCode: string | null) => void
  /** `nativo` (PRD 048): no celular da pessoa, o teclado é o do aparelho. */
  teclado?: Teclado
  descricao?: string
}) {
  // No keypad do iPad so entram digitos brasileiros. No teclado do aparelho
  // (link de documentos) a pessoa pode comecar com "+" e o codigo do pais.
  const [digits, setDigits] = useState('')
  const sendCode = useSendCode(clinicId)
  const valid = teclado === 'keypad' ? isValidMobile(digits) : isValidPhoneInput(digits)

  function submit() {
    const phone = toApiPhone(digits)
    sendCode.mutate(phone, { onSuccess: (devCode) => onSent(phone, devCode) })
  }

  function digitaNoAparelho(v: string) {
    if (v.trim().startsWith('+')) setDigits(`+${onlyDigits(v).slice(0, 15)}`)
    else setDigits(onlyDigits(v).slice(0, 11))
  }

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Qual é o seu celular?">{descricao}</StepHeader>
      {teclado === 'keypad' ? (
        <>
          <output
            aria-label="Celular digitado"
            className="mx-auto min-h-16 w-full max-w-sm rounded-2xl border-2 border-ink-200 bg-surface px-5 py-3 text-center font-display text-3xl font-semibold tabular-nums text-ink-900"
          >
            {digits ? formatPhone(digits) : <span className="text-ink-300">(00) 00000-0000</span>}
          </output>
          <Keypad value={digits} maxLength={11} onChange={setDigits} disabled={sendCode.isPending} />
        </>
      ) : (
        <form
          className="mx-auto w-full max-w-sm"
          onSubmit={(e) => {
            e.preventDefault()
            if (valid) submit()
          }}
        >
          <TextField
            label="Celular (WhatsApp)"
            value={formatPhoneInput(digits)}
            onChange={digitaNoAparelho}
            inputMode="tel"
            autoComplete="tel"
            placeholder="(00) 00000-0000"
            disabled={sendCode.isPending}
          />
          <p className="mt-2 text-sm text-ink-500">Número de fora do Brasil? Comece com + e o código do país.</p>
        </form>
      )}
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
