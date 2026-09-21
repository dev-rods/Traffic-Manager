/**
 * A agenda tem que abrir onde o trabalho está: nas próximas datas, e SÓ nelas.
 *
 * Com dados reais da Essência ela abria em 15/04, cinco meses no passado. A
 * primeira correção (20/09/2026) escolhia a página que CONTÉM a próxima data
 * futura, o que ainda deixava datas vencidas aparecerem antes dela quando a
 * primeira futura caía no meio da página.
 *
 * Agora as páginas são contadas a partir de hoje, então a página 0 nunca
 * mistura passado.
 */
import { describe, it, expect } from 'vitest'
import { janelaDaAgenda } from './agendaPaging'

const TAMANHO = 7

/** 5 datas vencidas e 4 futuras, com hoje em 30/08. */
const DATAS = [
  '2026-04-15', '2026-04-28', '2026-05-19', '2026-06-17', '2026-08-27',
  '2026-08-30', '2026-09-23', '2026-09-24', '2026-10-08',
]
const HOJE = '2026-08-30'

describe('janelaDaAgenda', () => {
  it('a primeira tela não traz nenhuma data vencida', () => {
    const { datas } = janelaDaAgenda(DATAS, HOJE, TAMANHO, null)

    expect(datas).toEqual(['2026-08-30', '2026-09-23', '2026-09-24', '2026-10-08'])
    expect(datas.every((d) => d >= HOJE)).toBe(true)
  })

  it('hoje conta como futuro: o dia ainda tem atendimento', () => {
    const { datas } = janelaDaAgenda(DATAS, HOJE, TAMANHO, null)

    expect(datas[0]).toBe(HOJE)
  })

  it('a página anterior é o passado, e para no que existe', () => {
    // 5 datas vencidas em páginas de 7: a página -1 é parcial e devolve as 5,
    // não um pedaço vazio.
    const { datas } = janelaDaAgenda(DATAS, HOJE, TAMANHO, -1)

    expect(datas).toEqual([
      '2026-04-15', '2026-04-28', '2026-05-19', '2026-06-17', '2026-08-27',
    ])
  })

  it('não deixa voltar além do começo da lista', () => {
    const { pagina, podeVoltar } = janelaDaAgenda(DATAS, HOJE, TAMANHO, -99)

    expect(pagina).toBe(-1)
    expect(podeVoltar).toBe(false)
  })

  it('não deixa avançar além do fim', () => {
    const { pagina, podeAvancar } = janelaDaAgenda(DATAS, HOJE, TAMANHO, 99)

    expect(pagina).toBe(0)
    expect(podeAvancar).toBe(false)
  })

  it('avança de sete em sete quando há futuro suficiente', () => {
    const futuras = Array.from({ length: 10 }, (_, i) => `2026-09-${String(i + 1).padStart(2, '0')}`)

    const primeira = janelaDaAgenda(futuras, '2026-09-01', TAMANHO, null)
    const segunda = janelaDaAgenda(futuras, '2026-09-01', TAMANHO, 1)

    expect(primeira.datas).toHaveLength(7)
    expect(primeira.podeAvancar).toBe(true)
    expect(segunda.datas).toEqual(['2026-09-08', '2026-09-09', '2026-09-10'])
    expect(segunda.podeAvancar).toBe(false)
  })

  it('sem passado, o botão de voltar fica desligado', () => {
    const { podeVoltar } = janelaDaAgenda(
      ['2026-09-23', '2026-09-24'], '2026-08-30', TAMANHO, null,
    )

    expect(podeVoltar).toBe(false)
  })

  it('sem datas futuras, abre no passado recente e não em janeiro', () => {
    // Clínica que parou de cadastrar. Mandar para o começo do histórico seria
    // pior do que mostrar o que aconteceu por último.
    const datas = [
      '2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08',
      '2026-01-09', '2026-01-12', '2026-01-13',
      '2026-01-14', '2026-01-15',
    ]

    const { datas: visiveis, pagina } = janelaDaAgenda(datas, '2026-08-30', TAMANHO, null)

    expect(pagina).toBe(-1)
    // As sete mais recentes, terminando na última cadastrada.
    expect(visiveis).toEqual([
      '2026-01-07', '2026-01-08', '2026-01-09',
      '2026-01-12', '2026-01-13', '2026-01-14', '2026-01-15',
    ])
  })

  it('lista vazia não quebra', () => {
    expect(janelaDaAgenda([], HOJE, TAMANHO, null)).toEqual({
      datas: [], pagina: 0, podeVoltar: false, podeAvancar: false,
    })
  })
})
