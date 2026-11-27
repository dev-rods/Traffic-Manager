import { useId, useState } from 'react'
import {
  BRASIL, OUTRO, PAISES, formataNumero, limiteDeDigitos, onlyDigits, paisDoNumero, telefoneDaApi,
} from '@/utils/ddi'

interface CelularComPaisProps {
  label?: string
  /** O número gravado, para editar (só dígitos, com ou sem `+`). */
  defaultValue?: string | null
  /** `55...` ou `+DDI...`; vazio enquanto o número estiver incompleto. */
  onChange: (apiPhone: string) => void
  error?: string
  placeholder?: string
}

const CAMPO = 'border rounded-lg px-3 py-2.5 text-sm bg-white transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500'

/**
 * Celular com país para os formulários do painel (PRD 067). Antes era texto
 * livre: `+1 202...` virava `551202...` no `normalizePhone`, e a recepção
 * precisava saber que tinha de digitar "+".
 */
export function CelularComPais({ label, defaultValue, onChange, error, placeholder }: CelularComPaisProps) {
  const id = useId()
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
    onChange(telefoneDaApi(codigo, d))
  }

  return (
    <div>
      {label && (
        <label htmlFor={`${id}-numero`} className="text-xs font-medium text-gray-500 block mb-1">{label}</label>
      )}
      <div className="flex gap-2">
        <select
          aria-label="País do telefone"
          value={pais}
          onChange={(e) => muda({ pais: e.target.value })}
          className={`${CAMPO} w-36 shrink-0 border-gray-200`}
        >
          {PAISES.map((p) => (
            <option key={p.ddi} value={p.ddi}>
              {p.nome} (+{p.ddi})
            </option>
          ))}
          <option value={OUTRO}>Outro país</option>
        </select>
        {pais === OUTRO && (
          <input
            aria-label="Código do país"
            inputMode="numeric"
            placeholder="Cód."
            value={ddiLivre}
            onChange={(e) => muda({ ddiLivre: onlyDigits(e.target.value).slice(0, 3) })}
            className={`${CAMPO} w-16 shrink-0 border-gray-200`}
          />
        )}
        <input
          id={`${id}-numero`}
          aria-label={label ? undefined : 'Telefone'}
          inputMode="tel"
          placeholder={placeholder ?? (ddi === BRASIL ? '(11) 99999-0000' : 'Sem o código do país')}
          value={formataNumero(ddi, digits)}
          onChange={(e) => muda({ digits: e.target.value })}
          aria-invalid={Boolean(error)}
          className={`${CAMPO} w-full min-w-0 ${error ? 'border-red-400' : 'border-gray-200'}`}
        />
      </div>
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  )
}
