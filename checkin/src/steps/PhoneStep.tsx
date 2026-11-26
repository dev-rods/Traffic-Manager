import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Keypad } from '@/components/ui/Keypad'
import { TextField } from '@/components/ui/TextField'
import { ErrorMessage, StepHeader } from '@/components/StepHeader'
import { useSendCode } from '@/hooks/useCheckin'
import {
  BRASIL, OUTRO, PAISES, formataNumero, limiteDeDigitos, montaTelefone, numeroValido, placeholderDoNumero,
} from '@/utils/ddi'
import { formatPhone, isValidMobile, onlyDigits, toApiPhone } from '@/utils/format'

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
  // Só no teclado do aparelho (link de documentos): o país do número, Brasil
  // por padrão. No keypad do iPad continua só o celular brasileiro.
  const [pais, setPais] = useState<string>(BRASIL)
  const [ddiLivre, setDdiLivre] = useState('')
  const ddi = pais === OUTRO ? onlyDigits(ddiLivre) : pais
  const sendCode = useSendCode(clinicId)
  const valid = teclado === 'keypad' ? isValidMobile(digits) : numeroValido(ddi, digits)

  function submit() {
    const phone = teclado === 'keypad' ? toApiPhone(digits) : montaTelefone(ddi, digits)
    sendCode.mutate(phone, { onSuccess: (devCode) => onSent(phone, devCode) })
  }

  function trocaPais(novo: string) {
    setPais(novo)
    setDigits((d) => onlyDigits(d).slice(0, limiteDeDigitos(novo === OUTRO ? '' : novo)))
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
          className="mx-auto flex w-full max-w-sm flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (valid) submit()
          }}
        >
          <div className="flex flex-col gap-2">
            <label htmlFor="pais-do-celular" className="font-display text-lg font-semibold text-ink-800">
              País
            </label>
            <select
              id="pais-do-celular"
              value={pais}
              onChange={(e) => trocaPais(e.target.value)}
              disabled={sendCode.isPending}
              className="min-h-16 w-full rounded-2xl border-2 border-ink-200 bg-surface px-4 text-xl text-ink-900 outline-none focus:border-accent-400"
            >
              {PAISES.map((p) => (
                <option key={p.ddi} value={p.ddi}>
                  {p.nome} (+{p.ddi})
                </option>
              ))}
              <option value={OUTRO}>Outro país</option>
            </select>
          </div>
          {pais === OUTRO ? (
            <TextField
              label="Código do país"
              value={ddiLivre}
              onChange={(v) => setDdiLivre(onlyDigits(v).slice(0, 3))}
              inputMode="numeric"
              placeholder="Ex.: 1, 44, 351"
              disabled={sendCode.isPending}
            />
          ) : null}
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
