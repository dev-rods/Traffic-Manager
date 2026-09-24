import type { NextVisitFilter, LastMessageFilter } from './contagemDeFiltros'

export interface FiltrosDePacientesProps {
  nextVisit: NextVisitFilter
  lastMessage: LastMessageFilter
  lastVisitBefore: string
  onNextVisit: (v: NextVisitFilter) => void
  onLastMessage: (v: LastMessageFilter) => void
  onLastVisitBefore: (v: string) => void
  /** Empilhado (drawer do celular) ou em linha (desktop). */
  empilhado?: boolean
}

/**
 * Os três filtros da lista de pacientes, num lugar só.
 *
 * Existiam soltos dentro da `PacientesPage`, numa linha `flex` sem quebra -
 * busca mais três campos que, somados, passam de 700px e estouram qualquer
 * tela de celular. Extrair permite que o mesmo JSX sirva à linha do desktop e
 * ao drawer do celular, sem duas cópias para manter em acordo.
 */
export function FiltrosDePacientes({
  nextVisit,
  lastMessage,
  lastVisitBefore,
  onNextVisit,
  onLastMessage,
  onLastVisitBefore,
  empilhado = false,
}: FiltrosDePacientesProps) {
  const campo =
    'border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer'

  return (
    <div className={empilhado ? 'flex flex-col gap-4 p-4' : 'flex items-center gap-3'}>
      <Campo rotulo="Próxima visita" empilhado={empilhado}>
        <select
          value={nextVisit}
          onChange={(e) => onNextVisit(e.target.value as NextVisitFilter)}
          aria-label="Próxima visita"
          className={`${campo} ${empilhado ? 'w-full' : ''}`}
        >
          <option value="all">Todas as visitas</option>
          <option value="with">Com próxima visita</option>
          <option value="without">Sem próxima visita</option>
        </select>
      </Campo>

      <Campo rotulo="Última mensagem" empilhado={empilhado}>
        <select
          value={lastMessage}
          onChange={(e) => onLastMessage(e.target.value as LastMessageFilter)}
          aria-label="Última mensagem"
          className={`${campo} ${empilhado ? 'w-full' : ''}`}
        >
          <option value="all">Última mensagem</option>
          <option value="7">Últimos 7 dias</option>
          <option value="15">Últimos 15 dias</option>
          <option value="30">Últimos 30 dias</option>
          <option value="60">Últimos 60 dias</option>
          <option value="never">Nunca contatado</option>
        </select>
      </Campo>

      <Campo rotulo="Última visita até" empilhado={empilhado}>
        <div className="relative">
          <input
            type="date"
            value={lastVisitBefore}
            onChange={(e) => onLastVisitBefore(e.target.value)}
            aria-label="Última visita até"
            title="Última visita até"
            className={`${campo} pr-8 ${empilhado ? 'w-full' : ''}`}
          />
          {lastVisitBefore && (
            <button
              type="button"
              onClick={() => onLastVisitBefore('')}
              aria-label="Limpar filtro de última visita"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm leading-none cursor-pointer"
            >
              ×
            </button>
          )}
        </div>
      </Campo>
    </div>
  )
}

/**
 * No drawer cada campo ganha rótulo: empilhados, um `select` fechado mostrando
 * "Todas as visitas" não diz de que ele filtra. Na linha do desktop o rótulo
 * some, porque lá o `aria-label` e o texto da opção já bastam e o espaço é
 * disputado.
 */
function Campo({
  rotulo,
  empilhado,
  children,
}: {
  rotulo: string
  empilhado: boolean
  children: React.ReactNode
}) {
  if (!empilhado) return <>{children}</>
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-gray-600">{rotulo}</span>
      {children}
    </label>
  )
}
