import { describe, expect, it } from 'vitest'
import { arredondaParaPasso, calculaDuracao, DURACAO_PADRAO } from './duracao'

/**
 * O preview do painel tem que dar o mesmo número que o backend. Se divergir, a
 * tela mostra um horário que o servidor não vai aceitar. Os casos aqui espelham
 * scheduler/tests/unit/test_duration_rules.py de propósito.
 */
describe('arredondaParaPasso', () => {
  it('arredonda para cima', () => {
    expect(arredondaParaPasso(21, 5)).toBe(25)
    expect(arredondaParaPasso(24, 5)).toBe(25)
  })

  it('deixa múltiplo exato intacto', () => {
    expect(arredondaParaPasso(25, 5)).toBe(25)
  })

  it('devolve o valor intacto com passo inválido', () => {
    expect(arredondaParaPasso(23, 0)).toBe(23)
    expect(arredondaParaPasso(23, -5)).toBe(23)
  })
})

describe('calculaDuracao', () => {
  it('sobe para o piso quando a soma é curta', () => {
    expect(calculaDuracao(4)).toBe(15)
    expect(calculaDuracao(10)).toBe(15)
  })

  it('desce para o teto quando a soma é longa', () => {
    expect(calculaDuracao(60)).toBe(50)
    expect(calculaDuracao(600)).toBe(50)
  })

  it('arredonda para múltiplo de cinco no meio', () => {
    expect(calculaDuracao(24)).toBe(25)
    expect(calculaDuracao(31)).toBe(35)
    expect(calculaDuracao(35)).toBe(35)
  })

  it('nunca sai do intervalo nem do passo', () => {
    for (let bruto = 0; bruto <= 120; bruto++) {
      const d = calculaDuracao(bruto)
      expect(d % DURACAO_PADRAO.step_minutes).toBe(0)
      expect(d).toBeGreaterThanOrEqual(DURACAO_PADRAO.floor_minutes)
      expect(d).toBeLessThanOrEqual(DURACAO_PADRAO.ceiling_minutes)
    }
  })

  it('trata zero, negativo e ausência de regra', () => {
    expect(calculaDuracao(0)).toBe(15)
    expect(calculaDuracao(-30)).toBe(15)
    expect(calculaDuracao(24, null)).toBe(25)
  })

  it('respeita a regra da clínica', () => {
    const regras = { floor_minutes: 30, ceiling_minutes: 90, step_minutes: 10 }

    expect(calculaDuracao(12, regras)).toBe(30)
    expect(calculaDuracao(62, regras)).toBe(70)
    expect(calculaDuracao(200, regras)).toBe(90)
  })

  it('com piso acima do teto, o piso vence', () => {
    expect(calculaDuracao(10, { floor_minutes: 40, ceiling_minutes: 20, step_minutes: 5 })).toBe(40)
  })

  it('é idempotente', () => {
    for (const bruto of [4, 24, 37, 60, 600]) {
      expect(calculaDuracao(calculaDuracao(bruto))).toBe(calculaDuracao(bruto))
    }
  })
})
