import { describe, expect, it } from 'vitest'
import { precoComDesconto } from './cadastroPaciente'
import {
  POLITICA_DA_CLINICA,
  SEM_DESCONTO,
  descontoDoAgendamento,
  parseDecimal,
  payloadDoDesconto,
  precoComDescontoEmCentavos,
  reaisParaCentavos,
  resumoDoDesconto,
  rotuloDaRazao,
  textoCurtoDoDesconto,
  textoDoDesconto,
  validaDesconto,
  type DescontoEscolhido,
} from './desconto'
import type { Cotacao } from '@/types'

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
  it('os cinco caminhos', () => {
    // "Sem desconto" é zero DE PROPÓSITO (PRD 053): a razão `none` impede o
    // backend de aplicar a política por cima.
    expect(payloadDoDesconto(SEM_DESCONTO)).toEqual({ discountPct: 0, discountReason: 'none' })
    expect(payloadDoDesconto(POLITICA_DA_CLINICA)).toEqual({ discountPolicy: true })
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
    expect(descontoDoAgendamento({ discount_pct: 0, discount_reason: 'none' })).toEqual(SEM_DESCONTO)
  })

  it('razão da política abre em "Política da clínica", não em Personalizado (PRD 053)', () => {
    for (const razao of ['first_session', 'tier_2', 'tier_3'] as const) {
      expect(descontoDoAgendamento({ discount_pct: 15, discount_reason: razao })).toEqual(POLITICA_DA_CLINICA)
    }
  })

  it('rótulo das razões, fonte única do popover, do Hoje e da cotação', () => {
    expect(rotuloDaRazao('first_session')).toBe('1ª sessão')
    expect(rotuloDaRazao('tier_2')).toBe('2-4 áreas')
    expect(rotuloDaRazao('tier_3')).toBe('5+ áreas')
    expect(rotuloDaRazao('partnership')).toBe('Parceria')
    expect(rotuloDaRazao('custom')).toBe('Personalizado')
    expect(rotuloDaRazao('none')).toBe('Sem desconto')
    expect(rotuloDaRazao(null)).toBe('Sem desconto')
    expect(rotuloDaRazao('zzz')).toBe('zzz')
  })

  it('texto da política para o resumo do 043', () => {
    expect(textoDoDesconto(POLITICA_DA_CLINICA)).toBe('política da clínica')
    expect(textoDoDesconto(POLITICA_DA_CLINICA, { discountReason: 'tier_2', discountPct: 15 })).toBe(
      'política da clínica (2-4 áreas: 15%)',
    )
    expect(textoDoDesconto(POLITICA_DA_CLINICA, { discountReason: null, discountPct: 0 })).toBe(
      'política da clínica (sem desconto)',
    )
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

  it('política: os centavos vêm da cotação, não de uma conta refeita aqui (PRD 053)', () => {
    const cotacao: Cotacao = {
      originalPriceCents: 19500, discountPct: 10, discountReason: 'first_session',
      finalPriceCents: 17550, areaCount: 1, isFirst: true,
    }
    expect(resumoDoDesconto(POLITICA_DA_CLINICA, 19500, cotacao)).toEqual({
      rotulo: '1ª sessão: 10%',
      descontoCents: 1950,
      totalCents: 17550,
    })
    expect(resumoDoDesconto(POLITICA_DA_CLINICA, 19500)).toBeNull()
    expect(resumoDoDesconto(POLITICA_DA_CLINICA, 19500, { ...cotacao, discountPct: 0, discountReason: null })).toBeNull()
  })
})
