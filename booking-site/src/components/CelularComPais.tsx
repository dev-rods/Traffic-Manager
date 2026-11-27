import { useState } from 'react'
import { Input } from './ui/Input'
import {
  BRASIL, OUTRO, PAISES, formataNumero, limiteDeDigitos, paisDoNumero, placeholderDoNumero, valorDoSite,
} from '@/utils/ddi'
import { normalizePhoneDigits as onlyDigits } from '@/utils/format'

interface CelularComPaisProps {
  id?: string
  /** Como estava (voltar não apaga): formatado, API ou com `+`. */
  defaultValue?: string
  /** A string do site: `(11) 99999-0000` ou `+12025550147`; vazio se incompleto fora do Brasil. */
  onChange: (valor: string) => void
  error?: string
  disabled?: boolean
}

/**
 * Celular com o país (PRD 067), no lugar do "comece com +" do PRD 033. Os
 * campos de país, código e número são estado daqui; para fora sai uma string
 * só, a mesma que o site sempre usou.
 */
export function CelularComPais({ id = 'phone', defaultValue = '', onChange, error, disabled }: CelularComPaisProps) {
  const [inicial] = useState(() => paisDoNumero(defaultValue))
  const [pais, setPais] = useState(inicial.pais)
  const [ddiLivre, setDdiLivre] = useState(inicial.ddiLivre)
  const [digits, setDigits] = useState(inicial.digits)
  const ddi = pais === OUTRO ? onlyDigits(ddiLivre) : pais

  function muda(proximo: { pais?: string; ddiLivre?: string; digits?: string }) {
    const p = proximo.pais ?? pais
    const livre = proximo.ddiLivre ?? ddiLivre
    const codigo = p === OUTRO ? onlyDigits(livre) : p
    const d = onlyDigits(proximo.digits ?? digits).slice(0, limiteDeDigitos(codigo))
    setPais(p)
    setDdiLivre(livre)
    setDigits(d)
    onChange(valorDoSite(codigo, d))
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-pais`} className="text-sm font-medium text-ink-700">
          País
        </label>
        <select
          id={`${id}-pais`}
          value={pais}
          disabled={disabled}
          onChange={(e) => muda({ pais: e.target.value })}
          className="h-12 rounded-xl border border-ink-200 bg-surface px-3 text-base text-ink-900 outline-none transition-colors focus:border-accent-700 focus:ring-2 focus:ring-accent-200"
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
        <Input
          id={`${id}-codigo`}
          label="Código do país"
          placeholder="Ex.: 1, 44, 351"
          inputMode="numeric"
          value={ddiLivre}
          disabled={disabled}
          onChange={(e) => muda({ ddiLivre: onlyDigits(e.target.value).slice(0, 3) })}
        />
      ) : null}
      <Input
        id={id}
        label="Celular (WhatsApp)"
        placeholder={placeholderDoNumero(ddi)}
        inputMode="tel"
        autoComplete={ddi === BRASIL ? 'tel-national' : 'tel'}
        value={formataNumero(ddi, digits)}
        error={error}
        disabled={disabled}
        hint={ddi === BRASIL ? 'Número de fora do Brasil? Escolha o país acima.' : 'Sem o código do país: ele já está escolhido acima.'}
        onChange={(e) => muda({ digits: e.target.value })}
      />
    </div>
  )
}
