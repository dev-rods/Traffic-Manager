import { useState } from 'react'

interface Props {
  dias: number | null
  ate: string | null
  salvando: boolean
  onChange: (dados: { agenda_days_ahead?: number | null; agenda_visible_until?: string | null }) => void
}

const PADRAO_DO_SERVIDOR = 14

/**
 * Até onde o funcionário enxerga a agenda.
 *
 * Os dois controles convivem, e o MAIS RESTRITIVO vence - é assim que o
 * servidor calcula, e a tela diz isso em vez de deixar a pessoa descobrir.
 *
 * O começo da janela é sempre hoje: funcionário não vê passado. A consequência
 * está escrita na tela porque ela muda a rotina da clínica - sessão não
 * registrada no mesmo dia passa a depender do administrador.
 *
 * O rascunho NÃO é sincronizado por efeito: o pai passa uma `key` derivada dos
 * valores do servidor, então a resposta remonta o campo. Sincronizar com
 * `useEffect` dispara render em cascata e o lint barra, com razão.
 */
export function JanelaDaAgendaField({ dias, ate, salvando, onChange }: Props) {
  const [rascunhoDias, setRascunhoDias] = useState(String(dias ?? PADRAO_DO_SERVIDOR))
  const [rascunhoAte, setRascunhoAte] = useState(ate ?? '')

  const salvarDias = () => {
    const n = Number(rascunhoDias)
    if (!Number.isInteger(n) || n < 0 || n > 365) {
      setRascunhoDias(String(dias ?? PADRAO_DO_SERVIDOR))
      return
    }
    if (n !== dias) onChange({ agenda_days_ahead: n })
  }

  const salvarAte = () => {
    const valor = rascunhoAte || null
    if (valor !== ate) onChange({ agenda_visible_until: valor })
  }

  return (
    <div className="rounded-md bg-gray-50 px-3 py-2.5 space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <label className="flex items-center gap-2 text-xs text-gray-600">
          Enxerga
          <input
            type="number"
            min={0}
            max={365}
            value={rascunhoDias}
            disabled={salvando}
            onChange={(e) => setRascunhoDias(e.target.value)}
            onBlur={salvarDias}
            className="w-16 rounded border border-gray-300 px-2 py-1 text-sm tabular-nums"
          />
          dias à frente
        </label>

        <label className="flex items-center gap-2 text-xs text-gray-600">
          e no máximo até
          <input
            type="date"
            value={rascunhoAte}
            disabled={salvando}
            onChange={(e) => setRascunhoAte(e.target.value)}
            onBlur={salvarAte}
            className="rounded border border-gray-300 px-2 py-1 text-sm"
          />
          {rascunhoAte && (
            <button
              type="button"
              disabled={salvando}
              onClick={() => {
                setRascunhoAte('')
                if (ate !== null) onChange({ agenda_visible_until: null })
              }}
              className="text-gray-400 hover:text-gray-700 cursor-pointer"
              title="Remover a data limite"
            >
              limpar
            </button>
          )}
        </label>
      </div>

      <p className="text-[11px] leading-snug text-gray-400">
        A agenda dele começa sempre em hoje - funcionário não vê datas passadas,
        então uma sessão não registrada no mesmo dia passa a depender de você.
        Quando os dois campos estão preenchidos, vale o mais restritivo.
      </p>
    </div>
  )
}
