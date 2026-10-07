export type NextVisitFilter = 'all' | 'with' | 'without'
export type LastMessageFilter = 'all' | '7' | '15' | '30' | '60' | 'never'

export interface EstadoDosFiltros {
  nextVisit: NextVisitFilter
  lastMessage: LastMessageFilter
  lastVisitBefore: string
}

/**
 * Quantos filtros estão ligados.
 *
 * Vira o número ao lado do botão "Filtros" em celular, onde os campos ficam
 * escondidos no drawer. Sem esse número, uma lista filtrada é
 * indistinguível de uma lista curta - e a pessoa conclui que a paciente
 * sumiu do sistema.
 *
 * Em arquivo separado do componente por causa do fast refresh: um módulo que
 * exporta componente E função perde o recarregamento a quente.
 *
 * O nome não é `filtrosDePacientes` porque no Windows isso colide com
 * `FiltrosDePacientes.tsx` - o sistema de arquivos não distingue maiúsculas, e
 * o TypeScript recusa os dois no mesmo projeto.
 */
export function contaFiltrosAtivos({
  nextVisit,
  lastMessage,
  lastVisitBefore,
}: EstadoDosFiltros): number {
  let n = 0
  if (nextVisit !== 'all') n += 1
  if (lastMessage !== 'all') n += 1
  if (lastVisitBefore) n += 1
  return n
}
