/**
 * Onde cada agendamento fica na coluna do dia.
 *
 * A agenda desenhava todo agendamento com `left: 2px; right: 2px` e altura
 * mínima de 30 minutos. Duas coisas davam errado juntas:
 *
 *   - Desde que o piso da duração caiu para 10 minutos (PR #46), uma sessão de
 *     10 min era desenhada com 30 e invadia as duas seguintes. Não era folga
 *     visual: era sobreposição garantida na agenda cheia.
 *   - Duas sessões no MESMO horário ficavam literalmente uma por cima da outra,
 *     e a de baixo sumia.
 *
 * Agora a altura é a duração real e quem se sobrepõe de verdade divide a
 * largura. É o layout de calendário de sempre: agrupa o que se toca, e dentro
 * do grupo cada um pega a primeira coluna livre.
 */

export interface Intervalo {
  /** Minutos desde a meia-noite. */
  inicio: number
  fim: number
}

export interface Posicao<T> {
  item: T
  /** Índice da coluna, começando em 0. */
  coluna: number
  /** Quantas colunas o grupo dele usa. Largura = 1/colunas. */
  colunas: number
}

/**
 * Distribui os itens em colunas, de modo que nada se sobreponha.
 *
 * Itens que não se tocam ficam cada um com a largura inteira - o caso comum, e
 * o que mantém a agenda legível num dia normal. Só quem colide divide espaço,
 * e divide apenas com quem colide: dois pares de sobreposição em horas
 * diferentes não estreitam um ao outro.
 */
export function distribuiEmColunas<T>(
  itens: T[],
  intervalo: (item: T) => Intervalo,
): Posicao<T>[] {
  const ordenados = [...itens].sort((a, b) => {
    const ia = intervalo(a)
    const ib = intervalo(b)
    if (ia.inicio !== ib.inicio) return ia.inicio - ib.inicio
    // Empate no início: o mais longo primeiro, para ele pegar a coluna 0 e a
    // leitura descer da esquerda para a direita.
    return ib.fim - ia.fim
  })

  const posicoes: Posicao<T>[] = []
  // Um grupo é um conjunto que se toca em cadeia: A colide com B, B com C, e
  // por isso os três dividem a largura mesmo que A e C não se toquem. Sem isso
  // B não caberia em lugar nenhum.
  let grupo: Posicao<T>[] = []
  let fimDoGrupo = -Infinity
  // O fim de cada coluna dentro do grupo atual.
  let fins: number[] = []

  const fechaGrupo = () => {
    const largura = fins.length || 1
    for (const p of grupo) p.colunas = largura
    posicoes.push(...grupo)
    grupo = []
    fins = []
    fimDoGrupo = -Infinity
  }

  for (const item of ordenados) {
    const { inicio, fim } = intervalo(item)

    // Começou depois de tudo que veio antes: o grupo anterior acabou.
    if (inicio >= fimDoGrupo && grupo.length > 0) fechaGrupo()

    // A primeira coluna cujo último item já terminou.
    let coluna = fins.findIndex((f) => f <= inicio)
    if (coluna === -1) {
      coluna = fins.length
      fins.push(fim)
    } else {
      fins[coluna] = fim
    }

    grupo.push({ item, coluna, colunas: 1 })
    fimDoGrupo = Math.max(fimDoGrupo, fim)
  }

  if (grupo.length > 0) fechaGrupo()

  return posicoes
}
