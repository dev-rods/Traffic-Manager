import { describe, expect, it } from 'vitest'
import { cadastroSchema, descontoParaApi } from './cadastroPaciente'
import { z } from 'zod'

const schema = z.object(cadastroSchema)

/**
 * `null` e `0` sao coisas diferentes, e o formulario e onde a confusao nasce:
 * campo de texto vazio vira `0` em qualquer conversao descuidada, e `0` no
 * banco significa "esta paciente nunca recebe desconto" - o oposto de "use a
 * politica da clinica".
 */
describe('desconto personalizado no formulario', () => {
  it('vazio vira null, nao zero', () => {
    expect(descontoParaApi('')).toBeNull()
    expect(descontoParaApi('   ')).toBeNull()
    expect(descontoParaApi(undefined)).toBeNull()
  })

  it('zero digitado vira zero, nao null', () => {
    expect(descontoParaApi('0')).toBe(0)
  })

  it('numero vira numero', () => {
    expect(descontoParaApi('30')).toBe(30)
  })

  it('aceita vazio e inteiros de 0 a 100', () => {
    for (const v of ['', '0', '30', '100', undefined]) {
      expect(schema.safeParse({ custom_discount_pct: v }).success).toBe(true)
    }
  })

  it('aceita duas casas decimais, com ponto ou virgula', () => {
    for (const v of ['12.5', '12,5', '33.33', '0.01']) {
      expect(schema.safeParse({ custom_discount_pct: v }).success).toBe(true)
    }
    expect(descontoParaApi('12,5')).toBe(12.5)
  })

  it('recusa fora da faixa, mais de duas casas e lixo', () => {
    for (const v of ['-1', '101', '12.555', '30%', 'abc']) {
      expect(schema.safeParse({ custom_discount_pct: v }).success).toBe(false)
    }
  })
})
