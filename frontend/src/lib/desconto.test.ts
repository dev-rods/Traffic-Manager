import { describe, expect, it } from 'vitest'
import { precoComDesconto } from './cadastroPaciente'

/**
 * A MESMA tabela existe em scheduler/tests/unit/test_desconto_contrato.py.
 *
 * O preço com desconto é calculado nas duas linguagens: a tela mostra o total
 * antes de salvar. Divergindo, a atendente combina um valor com a paciente e o
 * sistema cobra outro. Mudou de um lado, muda do outro, e os dois quebram juntos.
 */
describe('contrato com o backend', () => {
  const CASOS: Array<[number, number, number]> = [
    [20000, 0, 20000],
    [20000, 10, 18000],
    [20000, 12.5, 17500],
    [20000, 33.33, 13334],
    [20000, 100, 0],
    [19999, 10, 17999],
    [9500, 7.77, 8761],
    [1, 50, 0],
    [0, 50, 0],
  ]

  it.each(CASOS)('%i centavos com %f%% vira %i', (total, pct, esperado) => {
    expect(precoComDesconto(total, pct)).toBe(esperado)
  })

  it('trunca, nao arredonda', () => {
    // 33,33% de 20000 = 13334,0 exatos no truncamento; arredondar daria o mesmo,
    // mas 7,77% de 9500 separa os dois: 8761,35 trunca para 8761.
    expect(precoComDesconto(9500, 7.77)).toBe(8761)
  })
})
