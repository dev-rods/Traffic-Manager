/**
 * A mensagem do disparo em lote e as datas que entram nela.
 *
 * Vive fora do componente porque a tela de configurações também usa o texto
 * padrão como placeholder - exportar função de um arquivo de componente quebra
 * o fast refresh do Vite.
 */

/** Onde as datas marcadas entram no texto. */
export const MARCADOR_DE_DATAS = '{datas}'

/**
 * O texto padrão, com o marcador. É o que vale quando a clínica não cadastrou
 * um texto próprio em "Mensagem WhatsApp em lote".
 */
export const MENSAGEM_PADRAO = `Oi {nome}! Tudo bem?\n\nEstamos com novas datas disponíveis para agendamento: *${MARCADOR_DE_DATAS}*.\n\nGostaria de agendar sua sessão? Responda aqui que te ajudamos!`

export function formataDatas(datas: string[]): string {
  if (datas.length === 0) return 'em breve'
  return datas
    .map((d) => {
      const [, m, day] = d.split('-')
      return `${day}/${m}`
    })
    .join(', ')
}

/**
 * O texto com as datas no lugar do marcador. Texto sem marcador sai como está:
 * a clínica escreveu as datas à mão, ou não quer datas no texto.
 */
export function aplicaDatas(texto: string, datas: string[]): string {
  return texto.split(MARCADOR_DE_DATAS).join(formataDatas(datas))
}

/**
 * A mensagem que o modal mostra antes de a atendente editar: o texto da
 * clínica se houver, senão o padrão, sempre com as datas MARCADAS - não com
 * todas as disponíveis. Eram duas listas diferentes, e o texto prometia datas
 * que o bot não ia oferecer.
 */
export function mensagemDoDisparo(
  textoDaClinica: string | null | undefined,
  datas: string[]
): string {
  const base = textoDaClinica?.trim() ? textoDaClinica : MENSAGEM_PADRAO
  return aplicaDatas(base, datas)
}

/** Mantido para a tela de configurações, que mostra o padrão como placeholder. */
export function buildDefaultMessage(availableDates: string[]): string {
  return aplicaDatas(MENSAGEM_PADRAO, availableDates)
}
