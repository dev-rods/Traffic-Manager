import type { AplicacaoDeSessao, AplicacaoPayload } from '@/types'
import type { BlocoDeArea } from '@/lib/aplicacoes'
import { ROTULO_DO_METODO } from '@/lib/protocolo'

/**
 * Data e hora como a recepção lê. Pt-BR, curta, sem segundos.
 *
 * A trilha mostra muitas linhas juntas; segundo e ano completo viram ruído
 * sem ajudar ninguém a entender quando a alteração aconteceu.
 */
export function formatarData(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Data de sessão, sem hora. */
export function formatarDataDaSessao(iso: string): string {
  const [ano, mes, dia] = iso.split('-')
  if (!ano || !mes || !dia) return iso
  return `${dia}/${mes}/${ano}`
}

/**
 * Do formato do banco (snake_case) para o do corpo HTTP (camelCase).
 *
 * A conversão fica num lugar só pelo mesmo motivo do backend: campo com a
 * grafia errada é descartado EM SILÊNCIO — o parâmetro simplesmente não chega,
 * e ninguém levanta.
 */
export function paraPayload(a: AplicacaoDeSessao, indice: number): AplicacaoPayload {
  return {
    areaId: a.area_id,
    areaName: a.area_name,
    protocolAreaKey: a.protocol_area_key,
    method: a.method,
    fluenceJ: a.fluence_j,
    energyKj: a.energy_kj,
    stacks: a.stacks,
    passes: a.passes,
    displayOrder: indice,
  }
}

/** Uma aplicação em uma linha, para a leitura do histórico. */
export function resumoDaAplicacao(a: AplicacaoDeSessao): string {
  const partes: string[] = []
  if (a.fluence_j != null) partes.push(`${a.fluence_j} J`)
  if (a.energy_kj != null) partes.push(`${a.energy_kj} kJ`)
  if (a.stacks != null) partes.push(`${a.stacks} stacks`)
  if (a.passes != null) partes.push(`${a.passes} passadas`)
  return partes.join(' · ')
}

/**
 * Um método aplicado, em uma linha: `SHR · 8 J · 8 kJ`.
 *
 * Linha sem método nem valor diz isso em vez de sumir: no histórico, ausência
 * muda parece descuido da tela.
 */
export function resumoDaLinha(a: AplicacaoDeSessao): string {
  const metodo = a.method ? ROTULO_DO_METODO[a.method] : ''
  const valores = resumoDaAplicacao(a)
  if (!metodo && !valores) return 'sem parâmetro registrado'
  return [metodo, valores].filter(Boolean).join(' · ')
}

/** Os métodos de uma área juntos: `SHR · 8 J · 8 kJ / HR · 20 J · 1 kJ`. */
export function resumoDoBloco(bloco: BlocoDeArea): string {
  return bloco.linhas.map(resumoDaLinha).join(' / ')
}
