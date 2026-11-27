import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Keypad } from '@/components/ui/Keypad'
import { TextField } from '@/components/ui/TextField'
import { PaisDoCelular } from '@/components/PaisDoCelular'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useSendCode } from '@/hooks/useCheckin'
import {
  BRASIL, OUTRO, formataNumero, limiteDeDigitos, montaTelefone, numeroValido, placeholderDoNumero,
} from '@/utils/ddi'
import { onlyDigits } from '@/utils/format'

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
  const [digits, setDigits] = useState('')
  // O país do número, Brasil por padrão: no link de documentos desde 25/11 e
  // no keypad do iPad desde o PRD 067.
  const [pais, setPais] = useState<string>(BRASIL)
  const [ddiLivre, setDdiLivre] = useState('')
  const ddi = pais === OUTRO ? onlyDigits(ddiLivre) : pais
  const sendCode = useSendCode(clinicId)
  const valid = numeroValido(ddi, digits)

  function submit() {
    const phone = montaTelefone(ddi, digits)
    sendCode.mutate(phone, { onSuccess: (devCode) => onSent(phone, devCode) })
  }

  function trocaPais(novo: string) {
    setPais(novo)
    setDigits((d) => onlyDigits(d).slice(0, limiteDeDigitos(novo === OUTRO ? '' : novo)))
  }

  const seletor = (
    <PaisDoCelular
      pais={pais}
      ddiLivre={ddiLivre}
      onPais={trocaPais}
      onDdiLivre={setDdiLivre}
      disabled={sendCode.isPending}
    />
  )

  return (
    <div className="flex flex-col gap-8">
      <StepHeader title="Qual é o seu celular?">{descricao}</StepHeader>
      {teclado === 'keypad' ? (
        <div className="mx-auto flex w-full max-w-sm flex-col gap-4">
          {seletor}
          <output
            aria-label="Celular digitado"
            className="min-h-16 w-full rounded-2xl border-2 border-ink-200 bg-surface px-5 py-3 text-center font-display text-3xl font-semibold tabular-nums text-ink-900"
          >
            {digits ? (
              formataNumero(ddi, digits)
            ) : (
              <span className="text-ink-300">{ddi === BRASIL ? '(00) 00000-0000' : 'Sem o código do país'}</span>
            )}
          </output>
          <Keypad value={digits} maxLength={limiteDeDigitos(ddi)} onChange={setDigits} disabled={sendCode.isPending} />
        </div>
      ) : (
        <form
          className="mx-auto flex w-full max-w-sm flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (valid) submit()
          }}
        >
          {seletor}
          <TextField
            label="Celular (WhatsApp)"
            value={formataNumero(ddi, digits)}
            onChange={(v) => setDigits(onlyDigits(v).slice(0, limiteDeDigitos(ddi)))}
            inputMode="tel"
            autoComplete={ddi === BRASIL ? 'tel-national' : 'tel'}
            placeholder={placeholderDoNumero(ddi)}
            hint={ddi === BRASIL ? 'Número de fora do Brasil? Escolha o país acima.' : 'Sem o código do país: ele já está escolhido acima.'}
            disabled={sendCode.isPending}
          />
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
