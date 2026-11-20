import type { AplicacaoDeSessao, MetodoLaser, ParametroDoProtocolo, SkinType } from '@/types'
import { CAMPOS_POR_METODO, ROTULO_DO_CAMPO, metodosDaArea, parametrosIniciais } from '@/lib/protocolo'

/**
 * O que falta para o registro poder ser salvo (PRD 051).
 *
 * Espelho de `valida_aplicacoes` no backend: mesma ordem, mesmas mensagens.
 * A tela confere antes de mandar para destacar campo a campo; o backend
 * confere de novo porque tela não é a única cliente. Os índices são da lista
 * NORMALIZADA (`normaliza`), que é a que a tela indexa.
 */
export interface Pendencia {
  /** Índice na lista normalizada; -1 quando o registro inteiro está vazio. */
  indice: number
  area_name: string
  campo: 'method' | string
  mensagem: string
}

export const chaveDaPendencia = (p: Pick<Pendencia, 'indice' | 'campo'>) => `${p.indice}|${p.campo}`

export function pendenciasDoRegistro(aplicacoes: readonly AplicacaoDeSessao[]): Pendencia[] {
  if (aplicacoes.length === 0) {
    return [{ indice: -1, area_name: '', campo: 'method', mensagem: 'Informe ao menos uma área aplicada.' }]
  }
  const pendencias: Pendencia[] = []
  aplicacoes.forEach((a, indice) => {
    if (!a.method) {
      pendencias.push({ indice, area_name: a.area_name, campo: 'method', mensagem: `${a.area_name}: escolha o método.` })
      return
    }
    for (const campo of CAMPOS_POR_METODO[a.method] ?? []) {
      const valor = a[campo as keyof AplicacaoDeSessao] as number | null | undefined
      const rotulo = ROTULO_DO_CAMPO[campo] ?? campo
      if (valor === null || valor === undefined) {
        pendencias.push({ indice, area_name: a.area_name, campo, mensagem: `${a.area_name}: informe ${rotulo}.` })
      } else if (valor <= 0) {
        pendencias.push({ indice, area_name: a.area_name, campo, mensagem: `${a.area_name}: ${rotulo} precisa ser maior que zero.` })
      }
    }
  })
  return pendencias
}

/** Texto do erro geral: a própria mensagem quando é uma, um resumo quando são várias. */
export function resumoDasPendencias(pendencias: readonly Pendencia[]): string {
  if (pendencias.length === 1) return pendencias[0].mensagem
  return `Faltam ${pendencias.length} campos. Preencha os destacados ou remova a área que não foi aplicada.`
}

/**
 * Uma área da sessão e os métodos aplicados nela (PRD 030).
 *
 * No banco, cada aplicação continua sendo UMA linha por área + método — é isso
 * que mantém "que parâmetro usei na virilha da Maria?" um `WHERE`. O bloco é só
 * a forma de ler e editar: 1 área → N métodos → N parâmetros.
 */
export interface BlocoDeArea {
  chave: string
  area_name: string
  area_id: string | null
  protocol_area_key: string | null
  /** Origem comercial quando o bloco é parte de uma composta (PRD 052). */
  source_area_name: string | null
  /** Aplicações do bloco, na ordem em que aparecem. */
  linhas: AplicacaoDeSessao[]
}

/**
 * O que identifica a área. Nome + chave do protocolo, não só o nome: a
 * composta `Virilha Completa + ânus` vira duas áreas do protocolo diferentes, e
 * cada uma tem a sua sugestão de parâmetro.
 */
export function chaveDaArea(a: Pick<AplicacaoDeSessao, 'area_name' | 'protocol_area_key'>): string {
  return `${a.area_name}|${a.protocol_area_key ?? ''}`
}

/**
 * Agrupa na ordem da primeira ocorrência. Registros antigos que tinham a mesma
 * área adicionada duas vezes, longe uma da outra, caem no mesmo bloco — que é o
 * que eles sempre foram.
 */
export function agrupaPorArea(aplicacoes: readonly AplicacaoDeSessao[]): BlocoDeArea[] {
  const blocos = new Map<string, BlocoDeArea>()
  for (const ap of aplicacoes) {
    const chave = chaveDaArea(ap)
    const bloco = blocos.get(chave)
    if (bloco) {
      bloco.linhas.push(ap)
    } else {
      blocos.set(chave, {
        chave,
        area_name: ap.area_name,
        area_id: ap.area_id,
        protocol_area_key: ap.protocol_area_key,
        source_area_name: ap.source_area_name ?? null,
        linhas: [ap],
      })
    }
  }
  return [...blocos.values()]
}

/**
 * De volta para a lista plana, contígua por área e com `display_order`
 * renumerado. Toda edição passa por aqui, então o que vai para o backend sai
 * sempre na ordem em que a tela mostra.
 */
export function achata(blocos: readonly BlocoDeArea[]): AplicacaoDeSessao[] {
  return blocos
    .flatMap((b) => b.linhas)
    .map((ap, i) => (ap.display_order === i ? ap : { ...ap, display_order: i }))
}

/** A lista plana já reordenada por área, para a tela indexar com segurança. */
export function normaliza(aplicacoes: readonly AplicacaoDeSessao[]): AplicacaoDeSessao[] {
  return achata(agrupaPorArea(aplicacoes))
}

/**
 * Mais uma linha de método na área.
 *
 * Pré-escolhe o método só quando sobra exatamente UM com sugestão do protocolo
 * que ainda não está no bloco — mesma regra de "um só, já escolhe" de quando a
 * área entra. Sobrou mais de um (ou nenhum), fica em branco: escolher por ela
 * seria decidir conduta.
 */
export function adicionaMetodo(
  aplicacoes: readonly AplicacaoDeSessao[],
  chave: string,
  parametros: ParametroDoProtocolo[],
  skinType: SkinType | null
): AplicacaoDeSessao[] {
  const blocos = agrupaPorArea(aplicacoes)
  const bloco = blocos.find((b) => b.chave === chave)
  if (!bloco) return [...aplicacoes]

  const usados = new Set(bloco.linhas.map((l) => l.method))
  const restantes = metodosDaArea(parametros, bloco.protocol_area_key).filter((m) => !usados.has(m))
  const metodo: MetodoLaser | null = restantes.length === 1 ? restantes[0] : null
  const primeira = bloco.linhas[0]

  bloco.linhas = [
    ...bloco.linhas,
    {
      area_id: bloco.area_id,
      area_name: bloco.area_name,
      source_area_name: bloco.source_area_name,
      protocol_area_key: bloco.protocol_area_key,
      protocol_area_name: primeira?.protocol_area_name ?? null,
      method: metodo,
      ...parametrosIniciais(parametros, bloco.protocol_area_key, metodo, skinType),
      display_order: 0,
    },
  ]
  return achata(blocos)
}

/** Tira uma linha de método. O índice é o da lista plana normalizada. */
export function removeLinha(
  aplicacoes: readonly AplicacaoDeSessao[],
  indice: number
): AplicacaoDeSessao[] {
  return normaliza(aplicacoes.filter((_, i) => i !== indice))
}

/** Tira a área inteira, com todos os métodos. */
export function removeArea(
  aplicacoes: readonly AplicacaoDeSessao[],
  chave: string
): AplicacaoDeSessao[] {
  return normaliza(aplicacoes.filter((a) => chaveDaArea(a) !== chave))
}
