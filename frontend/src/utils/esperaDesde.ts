/**
 * Ha quanto tempo a conversa espera, em texto curto.
 *
 * A fila de especialista existe para ser triada por tempo: "3h" ao lado de um
 * nome e o que faz a recepcao abrir aquela conversa antes da outra. Data e hora
 * absolutas nao fazem isso - obrigam a pessoa a calcular a subtracao de cabeca,
 * e as 14:20 nao dizem nada sem saber que agora sao 17:40.
 *
 * Entrada em SEGUNDOS (epoch), que e o formato que o DynamoDB guarda em
 * `human_handoff_requested_at`. Milissegundos aqui dariam "agora mesmo" para
 * tudo, calado.
 */
export function esperaDesde(epochSegundos: number | null | undefined, agora = Date.now()): string {
  if (!epochSegundos) return ''

  const minutos = Math.floor((agora - epochSegundos * 1000) / 60_000)

  // Relogio do servidor adiantado em relacao ao do navegador da uma espera
  // negativa. "agora mesmo" e o unico texto honesto para isso.
  if (minutos < 1) return 'agora mesmo'
  if (minutos < 60) return `${minutos} min`

  const horas = Math.floor(minutos / 60)
  if (horas < 24) return `${horas}h`

  const dias = Math.floor(horas / 24)
  return dias === 1 ? '1 dia' : `${dias} dias`
}

/**
 * A espera passou de uma hora?
 *
 * Uma hora e a regra da clinica para "isso ja esta demorando": acima disso a
 * linha ganha destaque visual. Fica aqui, e nao espalhada na tela, porque e
 * uma decisao de negocio e nao de layout.
 */
export const LIMITE_DE_ESPERA_MINUTOS = 60

export function esperaDemais(
  epochSegundos: number | null | undefined,
  agora = Date.now(),
): boolean {
  if (!epochSegundos) return false
  return (agora - epochSegundos * 1000) / 60_000 >= LIMITE_DE_ESPERA_MINUTOS
}
