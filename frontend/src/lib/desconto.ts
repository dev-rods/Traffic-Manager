import type { Appointment } from '@/types'

/**
 * O desconto de um agendamento, nas duas formas (PRD 050).
 *
 * Percentual com até duas casas ("12,5") ou valor em reais ("20", "37,90").
 * Esta é a única casa da regra no painel: o campo, os dois modais, o resumo de
 * confirmação, o popover e o "Hoje" leem daqui. O backend faz a mesma conta em
 * `desconto_personalizado.py`, e o teste de contrato prende os dois.
 */

export type TipoDeDesconto = 'pct' | 'cents'
export type ModoDeDesconto = 'none' | 'partnership' | 'custom'

export interface DescontoEscolhido {
  modo: ModoDeDesconto
  /** Só importa em `custom`. */
  tipo: TipoDeDesconto
  /** O que está no campo, do jeito que foi digitado: "12,5", "20", "37,90". */
  texto: string
}

export const SEM_DESCONTO: DescontoEscolhido = { modo: 'none', tipo: 'pct', texto: '' }

/** "12,5" | "12.5" | "20" -> 12.5. Vazio, lixo ou mais de duas casas -> null. */
export function parseDecimal(texto: string): number | null {
  const limpo = texto.trim().replace(',', '.')
  if (!/^\d+(\.\d{1,2})?$/.test(limpo)) return null
  return Number(limpo)
}

/** Reais digitados -> centavos inteiros ("37,9" -> 3790). */
export function reaisParaCentavos(texto: string): number | null {
  const n = parseDecimal(texto)
  return n === null ? null : Math.round(n * 100)
}

/**
 * Preço com desconto percentual. TRUNCA, como o backend: era a divisão inteira
 * de sempre, e arredondar mudaria preços antigos.
 */
export function precoComDesconto(totalCents: number, pct: number): number {
  if (!totalCents) return totalCents || 0
  return Math.trunc((totalCents * (100 - pct)) / 100)
}

/** Preço com desconto em reais: subtração exata. A validação recusa antes de ficar negativo. */
export function precoComDescontoEmCentavos(totalCents: number, cents: number): number {
  return Math.max(totalCents - cents, 0)
}

export function formataReais(cents: number): string {
  return (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

/** 12.5 -> "12,5"; 10 -> "10"; 33.33 -> "33,33". */
export function formataPct(pct: number): string {
  return pct.toLocaleString('pt-BR', { maximumFractionDigits: 2 })
}

/**
 * A linha "Desconto (...)" e o total do resumo de preço. `null` quando não há
 * desconto a mostrar (sem desconto, ou personalizado ainda em branco/inválido).
 */
export function resumoDoDesconto(
  d: DescontoEscolhido,
  subtotalCents: number,
): { rotulo: string; descontoCents: number; totalCents: number } | null {
  if (d.modo === 'partnership') {
    return { rotulo: '100%', descontoCents: subtotalCents, totalCents: 0 }
  }
  if (d.modo !== 'custom') return null
  if (d.tipo === 'cents') {
    const cents = reaisParaCentavos(d.texto)
    if (cents === null || cents <= 0 || cents > subtotalCents) return null
    return {
      rotulo: formataReais(cents),
      descontoCents: cents,
      totalCents: precoComDescontoEmCentavos(subtotalCents, cents),
    }
  }
  const pct = parseDecimal(d.texto)
  if (pct === null || pct <= 0 || pct > 100) return null
  const total = precoComDesconto(subtotalCents, pct)
  return { rotulo: `${formataPct(pct)}%`, descontoCents: subtotalCents - total, totalCents: total }
}

/**
 * Mensagem para o submit, ou null. O subtotal é o teto do desconto em reais;
 * sem ele (áreas ainda não carregadas) o teto não é conferido aqui, e o
 * servidor recusa.
 */
export function validaDesconto(
  d: DescontoEscolhido,
  subtotalCents: number | undefined,
): string | null {
  if (d.modo !== 'custom') return null
  if (!d.texto.trim()) {
    return d.tipo === 'cents'
      ? 'Informe o valor do desconto em reais.'
      : 'Informe o percentual de desconto.'
  }
  if (d.tipo === 'cents') {
    const cents = reaisParaCentavos(d.texto)
    if (cents === null || cents <= 0) return 'Desconto em reais inválido. Use até duas casas, como 37,90.'
    if (subtotalCents !== undefined && cents > subtotalCents) {
      return 'O desconto não pode passar do valor da sessão.'
    }
    return null
  }
  const pct = parseDecimal(d.texto)
  if (pct === null || pct <= 0 || pct > 100) {
    return 'Informe um percentual entre 0,01 e 100, com até duas casas.'
  }
  return null
}

export interface PayloadDoDesconto {
  discountPct?: number
  discountCents?: number
  discountReason: string | null
}

/**
 * O pedaço do payload. `none` vira percentual zero sem razão, que é como a
 * edição tira um desconto; na criação quem chama omite o bloco quando é `none`.
 */
export function payloadDoDesconto(d: DescontoEscolhido): PayloadDoDesconto {
  if (d.modo === 'partnership') return { discountPct: 100, discountReason: 'partnership' }
  if (d.modo === 'custom') {
    if (d.tipo === 'cents') {
      return { discountCents: reaisParaCentavos(d.texto) ?? 0, discountReason: 'custom' }
    }
    return { discountPct: parseDecimal(d.texto) ?? 0, discountReason: 'custom' }
  }
  return { discountPct: 0, discountReason: null }
}

type Gravado = Pick<Appointment, 'discount_pct' | 'discount_reason'> & {
  /** Opcional até o prod servir a coluna: `undefined` conta como nulo. */
  discount_cents?: number | null
}

/** Do agendamento gravado para o estado do campo. */
export function descontoDoAgendamento(a: Gravado): DescontoEscolhido {
  if (a.discount_reason === 'partnership') return { modo: 'partnership', tipo: 'pct', texto: '' }
  if (a.discount_cents) {
    return { modo: 'custom', tipo: 'cents', texto: (a.discount_cents / 100).toFixed(2).replace('.', ',') }
  }
  const pct = a.discount_pct ?? 0
  if (a.discount_reason === 'custom' || pct > 0) {
    return { modo: 'custom', tipo: 'pct', texto: formataPct(pct) }
  }
  return SEM_DESCONTO
}

/** Há desconto para mostrar? Cobre as duas formas. */
export function temDesconto(a: Pick<Gravado, 'discount_pct' | 'discount_cents'>): boolean {
  return (a.discount_pct ?? 0) > 0 || Boolean(a.discount_cents)
}

/** "-12,5%" | "-R$ 20,00", para popover e "Hoje". */
export function textoCurtoDoDesconto(a: Pick<Gravado, 'discount_pct' | 'discount_cents'>): string {
  if (a.discount_cents) return `-${formataReais(a.discount_cents)}`
  return `-${formataPct(a.discount_pct ?? 0)}%`
}

/** "12,5%" | "R$ 20,00" | "parceria (100%)" | "sem desconto", para o resumo do PRD 043. */
export function textoDoDesconto(d: DescontoEscolhido): string {
  if (d.modo === 'partnership') return 'parceria (100%)'
  if (d.modo === 'custom') {
    if (d.tipo === 'cents') {
      const cents = reaisParaCentavos(d.texto)
      return cents && cents > 0 ? formataReais(cents) : 'sem desconto'
    }
    const pct = parseDecimal(d.texto)
    return pct && pct > 0 ? `${formataPct(pct)}%` : 'sem desconto'
  }
  return 'sem desconto'
}
