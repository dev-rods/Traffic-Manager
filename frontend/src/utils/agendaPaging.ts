/**
 * Em que página a agenda deve abrir.
 *
 * A lista de datas é histórica e cresce pelo início: as mais antigas ficam na
 * página 0. Abrir ali mostrava abril para quem precisa de setembro, e o custo
 * aumenta a cada mês novo. O trabalho de uma clínica está sempre à frente.
 */
export function paginaDaProximaData(
  datasOrdenadas: string[],
  hoje: string,
  tamanhoDaPagina: number,
): number {
  if (datasOrdenadas.length === 0) return 0

  const indice = datasOrdenadas.findIndex((data) => data >= hoje)

  // Sem data futura, a última página: o passado recente é mais útil que o
  // começo do histórico para quem só quer conferir o que aconteceu.
  if (indice === -1) {
    return Math.max(0, Math.ceil(datasOrdenadas.length / tamanhoDaPagina) - 1)
  }

  return Math.floor(indice / tamanhoDaPagina)
}
