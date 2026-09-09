import { describe, expect, it } from 'vitest'
import { arredondaParaPasso, calculaDuracao, DURACAO_PADRAO } from './duracao'

/**
 * O preview do painel tem que dar o mesmo número que o backend. Se divergir, a
 * tela mostra um horário que o servidor não vai aceitar. Os casos aqui espelham
 * scheduler/tests/unit/test_duration_rules.py de propósito.
 */
describe('arredondaParaPasso', () => {
  // Era para cima. A Bruna tinha 17 minutos (axilas 5 + virilha 12) virando
  // 20, e a clínica perdia 3 minutos de sala em toda sessão dessa combinação.
  it('arredonda para o mais próximo', () => {
    expect(arredondaParaPasso(17, 5)).toBe(15)
    expect(arredondaParaPasso(18, 5)).toBe(20)
    expect(arredondaParaPasso(21, 5)).toBe(20)
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

  it('arredonda para o múltiplo de cinco mais próximo', () => {
    expect(calculaDuracao(17)).toBe(15)
    expect(calculaDuracao(24)).toBe(25)
    expect(calculaDuracao(31)).toBe(30)
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
    expect(calculaDuracao(62, regras)).toBe(60)
    expect(calculaDuracao(67, regras)).toBe(70)
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

/**
 * A MESMA tabela existe em scheduler/tests/unit/test_duration_rules.py.
 *
 * A regra de duração vive em duas linguagens porque a tela precisa mostrar o
 * horário de fim antes de salvar. Divergindo, a tela promete uma coisa e o
 * banco grava outra - e o paciente é quem descobre. Esta tabela é o contrato:
 * mudou de um lado, muda do outro, e os dois testes quebram juntos.
 */
describe('contrato com o backend', () => {
  const CASOS: Array<[number, number]> = [
    [0, 15],
    [2, 15],
    [12, 15],
    [17, 15],
    [18, 20],
    [21, 20],
    [24, 25],
    [31, 30],
    [35, 35],
    [37, 35],
    [38, 40],
    [52, 50],
    [200, 50],
  ]

  it.each(CASOS)('soma %i vira %i', (bruto, esperado) => {
    expect(calculaDuracao(bruto)).toBe(esperado)
  })
})
