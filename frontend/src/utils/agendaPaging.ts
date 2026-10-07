/**
 * Qual fatia de datas a agenda mostra.
 *
 * A lista de datas é histórica e cresce pelo início: as mais antigas ficam
 * primeiro. Paginar do começo do array mostrava abril para quem precisa de
 * setembro, e o custo aumentava a cada mês novo.
 *
 * A correção anterior escolhia a página QUE CONTÉM a próxima data futura. Isso
 * resolvia o pior caso, mas a primeira tela continuava misturando passado: se a
 * próxima data caía na quarta posição de uma página de sete, três datas já
 * vencidas apareciam antes dela.
 *
 * Aqui as páginas são contadas A PARTIR DE HOJE, e não do começo do array:
 *
 *     ... -2   -1 | 0    1    2 ...
 *          passado ^ hoje    futuro
 *
 * A página 0 é sempre exatamente as próximas `tamanho` datas, sem nenhuma
 * vencida junto. O passado não some: continua em páginas negativas, alcançáveis
 * pelo botão de voltar.
 */

export interface JanelaDaAgenda {
  /** As datas visíveis nesta página. */
  datas: string[]
  /** A página de fato usada, já corrigida para os limites. */
  pagina: number
  podeVoltar: boolean
  podeAvancar: boolean
}

export function janelaDaAgenda(
  datasOrdenadas: string[],
  hoje: string,
  tamanho: number,
  paginaPedida: number | null,
): JanelaDaAgenda {
  if (datasOrdenadas.length === 0) {
    return { datas: [], pagina: 0, podeVoltar: false, podeAvancar: false }
  }

  // Onde o futuro começa. Sem data futura, a âncora é o fim da lista.
  const indiceDeHoje = datasOrdenadas.findIndex((data) => data >= hoje)
  const ancora = indiceDeHoje === -1 ? datasOrdenadas.length : indiceDeHoje

  const paginasAtras = Math.ceil(ancora / tamanho)
  const paginasAFrente = Math.ceil((datasOrdenadas.length - ancora) / tamanho)

  const paginaMinima = -paginasAtras
  // Sem nenhuma data futura, a última página do passado é o melhor lugar para
  // abrir: quem só quer conferir o que aconteceu não quer começar em janeiro.
  const paginaMaxima = paginasAFrente > 0 ? paginasAFrente - 1 : -1
  const paginaPadrao = paginasAFrente > 0 ? 0 : -1

  const pagina = Math.min(
    Math.max(paginaPedida ?? paginaPadrao, paginaMinima),
    paginaMaxima,
  )

  // `bruto` pode ser negativo quando a última página do passado é parcial: com
  // 3 datas vencidas e páginas de 7, a página -1 começa em -4. Cortar em zero
  // devolve as 3 que existem, e não um pedaço vazio.
  const bruto = ancora + pagina * tamanho
  const datas = datasOrdenadas.slice(Math.max(0, bruto), bruto + tamanho)

  return {
    datas,
    pagina,
    podeVoltar: pagina > paginaMinima,
    podeAvancar: pagina < paginaMaxima,
  }
}
