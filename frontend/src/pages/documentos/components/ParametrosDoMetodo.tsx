import type { AplicacaoDeSessao, MetodoLaser } from '@/types'
import { CAMPOS_POR_METODO, ROTULO_DO_CAMPO, bolinhas } from '@/lib/protocolo'

interface ParametrosDoMetodoProps {
  aplicacao: AplicacaoDeSessao
  onChange: (campo: string, valor: number | null) => void
  disabled?: boolean
}

const CAMPO_NUMERICO = 'w-24 rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500'

/**
 * Os campos de parâmetro, que mudam conforme o método.
 *
 *   SHR            Fluência (J) + Energia (kJ)
 *   SHR Stacking   Fluência (J) + Stacks + Passadas
 *   HR             Fluência (J) + Energia (kJ)
 *
 * Espelha CAMPOS_POR_METODO, que espelha o backend. Os rótulos são os dos PDFs.
 *
 * Stacks aparecem com as bolinhas do material (●●●) ao lado do número: é assim
 * que ela lê a tabela impressa, e reconhecer bate mais rápido do que converter.
 */
export function ParametrosDoMetodo({ aplicacao, onChange, disabled }: ParametrosDoMetodoProps) {
  const metodo = aplicacao.method as MetodoLaser | null

  if (!metodo) {
    return (
      <span className="text-xs text-gray-400">
        Escolha o método para informar os parâmetros
      </span>
    )
  }

  const campos = CAMPOS_POR_METODO[metodo] ?? []

  return (
    <div className="flex flex-wrap items-end gap-3">
      {campos.map((campo) => {
        const valor = aplicacao[campo as keyof AplicacaoDeSessao] as number | null
        return (
          <label key={campo} className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-gray-500">
              {ROTULO_DO_CAMPO[campo] ?? campo}
            </span>
            <span className="flex items-center gap-1.5">
              <input
                type="number"
                inputMode="decimal"
                step={campo === 'fluence_j' || campo === 'energy_kj' ? '0.5' : '1'}
                min={campo === 'stacks' ? 2 : undefined}
                max={campo === 'stacks' ? 5 : undefined}
                value={valor ?? ''}
                disabled={disabled}
                onChange={(e) =>
                  onChange(campo, e.target.value === '' ? null : Number(e.target.value))
                }
                className={CAMPO_NUMERICO}
              />
              {campo === 'stacks' && valor ? (
                <span className="select-none text-xs text-gray-400" aria-hidden="true">
                  {bolinhas(valor)}
                </span>
              ) : null}
            </span>
          </label>
        )
      })}
    </div>
  )
}
