import { describe, expect, it } from 'vitest'
import { precoComDesconto } from './cadastroPaciente'
import {
  SEM_DESCONTO,
  descontoDoAgendamento,
  parseDecimal,
  payloadDoDesconto,
  precoComDescontoEmCentavos,
  reaisParaCentavos,
  resumoDoDesconto,
  textoCurtoDoDesconto,
  validaDesconto,
  type DescontoEscolhido,
} from './desconto'

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

/** A MESMA tabela em scheduler/tests/unit/test_desconto_contrato.py (PRD 050). */
describe('contrato em centavos', () => {
  it.each([
    [19500, 2000, 17500],
    [1, 1, 0],
    [20000, 20000, 0],
    [0, 0, 0],
  ])('%i menos %i centavos vira %i', (total, cents, esperado) => {
    expect(precoComDescontoEmCentavos(total, cents)).toBe(esperado)
  })
})

const custom = (over: Partial<DescontoEscolhido>): DescontoEscolhido => ({
  modo: 'custom',
  tipo: 'pct',
  texto: '',
  ...over,
})

describe('parse do que foi digitado', () => {
  it('vírgula ou ponto, até duas casas', () => {
    expect(parseDecimal('12,5')).toBe(12.5)
    expect(parseDecimal('12.5')).toBe(12.5)
    expect(parseDecimal(' 20 ')).toBe(20)
    expect(parseDecimal('0,01')).toBe(0.01)
  })

  it('recusa vazio, lixo e três casas', () => {
    for (const t of ['', '12,555', 'abc', '12%', '-1', '1,2,3']) {
      expect(parseDecimal(t)).toBeNull()
    }
  })

  it('reais viram centavos inteiros', () => {
    expect(reaisParaCentavos('37,9')).toBe(3790)
    expect(reaisParaCentavos('20')).toBe(2000)
    expect(reaisParaCentavos('0,1')).toBe(10)
  })
})

describe('validaDesconto', () => {
  it('sem desconto e parceria nunca erram', () => {
    expect(validaDesconto(SEM_DESCONTO, undefined)).toBeNull()
    expect(validaDesconto({ ...SEM_DESCONTO, modo: 'partnership' }, 0)).toBeNull()
  })

  it('personalizado em branco pede o valor', () => {
    expect(validaDesconto(custom({}), 19500)).toMatch(/Informe o percentual/)
    expect(validaDesconto(custom({ tipo: 'cents' }), 19500)).toMatch(/Informe o valor/)
  })

  it('percentual fora de 0,01..100 ou com três casas', () => {
    for (const t of ['0', '100,01', '12,555']) {
      expect(validaDesconto(custom({ texto: t }), 19500)).toMatch(/entre 0,01 e 100/)
    }
    expect(validaDesconto(custom({ texto: '100' }), 19500)).toBeNull()
  })

  it('reais acima do subtotal; sem subtotal o servidor decide', () => {
    expect(validaDesconto(custom({ tipo: 'cents', texto: '250' }), 19500)).toMatch(/não pode passar/)
    expect(validaDesconto(custom({ tipo: 'cents', texto: '195' }), 19500)).toBeNull()
    expect(validaDesconto(custom({ tipo: 'cents', texto: '250' }), undefined)).toBeNull()
  })
})

describe('payloadDoDesconto', () => {
  it('os quatro caminhos', () => {
    expect(payloadDoDesconto(SEM_DESCONTO)).toEqual({ discountPct: 0, discountReason: null })
    expect(payloadDoDesconto({ ...SEM_DESCONTO, modo: 'partnership' })).toEqual({
      discountPct: 100,
      discountReason: 'partnership',
    })
    expect(payloadDoDesconto(custom({ texto: '12,5' }))).toEqual({ discountPct: 12.5, discountReason: 'custom' })
    expect(payloadDoDesconto(custom({ tipo: 'cents', texto: '20' }))).toEqual({
      discountCents: 2000,
      discountReason: 'custom',
    })
  })
})

describe('do agendamento gravado para o campo, e de volta', () => {
  it('reais gravados viram R$ no campo, mesmo com o percentual equivalente ao lado', () => {
    expect(descontoDoAgendamento({ discount_pct: 10.26, discount_cents: 2000, discount_reason: 'custom' })).toEqual(
      custom({ tipo: 'cents', texto: '20,00' }),
    )
  })

  it('percentual gravado vira % com vírgula', () => {
    expect(descontoDoAgendamento({ discount_pct: 12.5, discount_cents: null, discount_reason: 'custom' })).toEqual(
      custom({ texto: '12,5' }),
    )
  })

  it('a coluna ausente (API antiga) conta como percentual', () => {
    expect(descontoDoAgendamento({ discount_pct: 30, discount_reason: 'custom' })).toEqual(custom({ texto: '30' }))
    expect(descontoDoAgendamento({ discount_pct: 0, discount_reason: null })).toEqual(SEM_DESCONTO)
  })

  it('texto curto para popover e Hoje', () => {
    expect(textoCurtoDoDesconto({ discount_pct: 12.5, discount_cents: null })).toBe('-12,5%')
    expect(textoCurtoDoDesconto({ discount_pct: 10, discount_cents: null })).toBe('-10%')
    expect(textoCurtoDoDesconto({ discount_pct: 10.26, discount_cents: 2000 })).toBe('-R$ 20,00')
  })
})

describe('resumoDoDesconto', () => {
  it('a mesma conta do servidor, nas duas formas', () => {
    expect(resumoDoDesconto(custom({ texto: '12,5' }), 19500)).toEqual({
      rotulo: '12,5%',
      descontoCents: 2438,
      totalCents: 17062,
    })
    expect(resumoDoDesconto(custom({ tipo: 'cents', texto: '20' }), 19500)).toEqual({
      rotulo: 'R$ 20,00',
      descontoCents: 2000,
      totalCents: 17500,
    })
  })

  it('em branco, inválido ou acima do subtotal não mostra linha', () => {
    expect(resumoDoDesconto(custom({}), 19500)).toBeNull()
    expect(resumoDoDesconto(custom({ tipo: 'cents', texto: '250' }), 19500)).toBeNull()
    expect(resumoDoDesconto(SEM_DESCONTO, 19500)).toBeNull()
  })
})
