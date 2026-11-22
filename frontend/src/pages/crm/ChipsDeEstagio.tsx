import type { LeadStage } from '@/types'
import { ESTAGIOS, ORDEM_DA_FILA } from './estagios'

interface ChipsDeEstagioProps {
  contagem: Record<string, number>
  selecionados: LeadStage[]
  onToggle: (stage: LeadStage) => void
  mostrarMais: boolean
  onMostrarMais: () => void
}

/** Um chip por estagio com a contagem. Multi-selecao. "mais" revela Nao e lead. */
export function ChipsDeEstagio({ contagem, selecionados, onToggle, mostrarMais, onMostrarMais }: ChipsDeEstagioProps) {
  const lista: LeadStage[] = mostrarMais ? [...ORDEM_DA_FILA, 'NAO_E_LEAD'] : ORDEM_DA_FILA
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por estágio">
      {lista.map((stage) => {
        const ativo = selecionados.includes(stage)
        return (
          <button
            key={stage}
            type="button"
            aria-pressed={ativo}
            onClick={() => onToggle(stage)}
            title={ESTAGIOS[stage].descricao}
            className={[
              'inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm transition-colors duration-150 cursor-pointer min-h-11',
              ativo ? 'bg-brand-600 text-white' : 'bg-gray-50 text-gray-700 hover:bg-gray-100',
            ].join(' ')}
          >
            {ESTAGIOS[stage].label}
            <span className={ativo ? 'text-white/80 tabular-nums' : 'text-gray-400 tabular-nums'}>
              {contagem[stage] ?? 0}
            </span>
          </button>
        )
      })}
      {!mostrarMais && (
        <button
          type="button"
          onClick={onMostrarMais}
          className="text-sm text-gray-500 underline-offset-2 hover:underline cursor-pointer min-h-11 px-2"
        >
          mais
        </button>
      )}
    </div>
  )
}
