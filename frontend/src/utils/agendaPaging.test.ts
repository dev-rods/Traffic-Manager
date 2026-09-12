/**
 * A agenda tem que abrir onde o trabalho está: nas próximas datas.
 *
 * Com dados reais da Essência ela abria em 15/04, cinco meses no passado, e
 * exigia dois cliques até 23/09. O problema piora sozinho: cada mês que passa
 * empurra a primeira data futura para mais longe do início da lista.
 */
import { describe, it, expect } from 'vitest'
import { paginaDaProximaData } from './agendaPaging'

const TAMANHO = 7

describe('paginaDaProximaData', () => {
  it('abre na página que contém a primeira data futura', () => {
    const datas = [
      '2026-04-15', '2026-04-28', '2026-04-29', '2026-05-19',
      '2026-05-27', '2026-05-28', '2026-06-17', // fim da página 0
      '2026-06-24', '2026-07-01', '2026-07-15', '2026-07-22',
      '2026-08-05', '2026-08-12', '2026-08-27', // fim da página 1
      '2026-09-23', '2026-09-24', // página 2 — a primeira futura
    ]

    expect(paginaDaProximaData(datas, '2026-08-30', TAMANHO)).toBe(2)
  })

  it('inclui o próprio dia de hoje, que ainda tem atendimento', () => {
    const datas = ['2026-08-27', '2026-08-30', '2026-09-23']

    expect(paginaDaProximaData(datas, '2026-08-30', TAMANHO)).toBe(0)
  })

  it('sem datas futuras, mostra a última página em vez de voltar ao começo', () => {
    // Clínica que parou de cadastrar: o mais recente é mais útil que abril.
    const datas = [
      '2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08',
      '2026-01-09', '2026-01-12', '2026-01-13', // página 0
      '2026-01-14', '2026-01-15', // página 1
    ]

    expect(paginaDaProximaData(datas, '2026-08-30', TAMANHO)).toBe(1)
  })

  it('lista vazia não quebra', () => {
    expect(paginaDaProximaData([], '2026-08-30', TAMANHO)).toBe(0)
  })

  it('primeira data já é futura', () => {
    const datas = ['2026-09-23', '2026-09-24', '2026-10-08']

    expect(paginaDaProximaData(datas, '2026-08-30', TAMANHO)).toBe(0)
  })
})
