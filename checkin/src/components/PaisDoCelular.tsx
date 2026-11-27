import { TextField } from '@/components/ui/TextField'
import { OUTRO, PAISES } from '@/utils/ddi'
import { onlyDigits } from '@/utils/format'

/**
 * País do celular (25/11, PR #276; extraído no PRD 067 para o keypad do iPad e
 * o celular do responsável). Brasil por padrão, lista fixa e "Outro país" com
 * o código à mão.
 */
export function PaisDoCelular({
  id = 'pais-do-celular',
  label = 'País',
  pais,
  ddiLivre,
  onPais,
  onDdiLivre,
  disabled,
  compacto = false,
}: {
  id?: string
  label?: string
  pais: string
  ddiLivre: string
  onPais: (pais: string) => void
  onDdiLivre: (ddi: string) => void
  disabled?: boolean
  /** Keypad do iPad deitado: o rótulo vira só para leitor de tela (o seletor já diz "Brasil (+55)"), senão o botão sai da tela. */
  compacto?: boolean
}) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <label htmlFor={id} className={compacto ? 'sr-only' : 'font-display text-lg font-semibold text-ink-800'}>
          {label}
        </label>
        <select
          id={id}
          value={pais}
          onChange={(e) => onPais(e.target.value)}
          disabled={disabled}
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
          id={`${id}-codigo`}
          label="Código do país"
          value={ddiLivre}
          onChange={(v) => onDdiLivre(onlyDigits(v).slice(0, 3))}
          inputMode="numeric"
          placeholder="Ex.: 1, 44, 351"
          disabled={disabled}
        />
      ) : null}
    </>
  )
}
