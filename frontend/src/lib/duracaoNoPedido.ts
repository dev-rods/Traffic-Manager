/**
 * Quando o pedido de edição precisa carregar a duração manual.
 *
 * O backend trata "trocar a área" como **descartar o override anterior** -
 * decisão do André em 17/09/2026, e ela continua certa: aquele valor foi
 * escolhido para outras áreas.
 *
 * A consequência é que, nesse caminho, o servidor descarta **a menos que o
 * pedido traga uma duração**. Ou seja, quando as áreas mudam, restabelecer o
 * mesmo número não é "não mudou": é preciso dizer de novo.
 *
 * Sem isto, o caso relatado em 21/09/2026:
 *
 *   1. a sessão tem 10 min fixados, e cabe no horário
 *   2. a atendente remove uma área; a tela zera o campo e avisa "descartada"
 *   3. ela redigita 10
 *   4. `10 !== 10` - o painel conclui "não mudou" e NÃO manda a duração
 *   5. o servidor descarta o override, recalcula pelas áreas e acusa conflito
 *
 * O número na tela dizia 10 e o servidor gravava outro. É a mesma família do
 * defeito de 20/09: uma decisão tomada com um número que o pedido já
 * substituiu - só que desta vez quem perdeu o número foi o pedido.
 */
export function precisaMandarDuracao({
  manualNaTela,
  manualNoServidor,
  mudouAreaOuServico,
}: {
  /** O que está no campo agora. `null` = seguir o cálculo. */
  manualNaTela: number | null
  /** O que o servidor tem hoje para este agendamento. */
  manualNoServidor: number | null
  /** As áreas ou o serviço foram alterados neste mesmo pedido. */
  mudouAreaOuServico: boolean
}): boolean {
  if (manualNaTela !== manualNoServidor) return true

  /**
   * Valor igual ao do servidor, mas as áreas mudaram: o servidor vai descartar
   * se o pedido ficar calado. Reafirmar é obrigatório.
   *
   * Só quando há um valor a reafirmar. Com `null` dos dois lados não há
   * override nenhum, e mandar `null` seria pedir para soltar o que não existe.
   */
  return mudouAreaOuServico && manualNaTela !== null
}
