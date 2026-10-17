import { describe, expect, it } from 'vitest'
import {
  formatCurrencyBRL,
  formatDateBR,
  formatPhoneDisplay,
  hasPrice,
  formatPhoneInput,
  isValidBrPhone,
  normalizePhoneDigits,
  toApiPhone,
} from './format'

describe('formatCurrencyBRL', () => {
  it('formata centavos como moeda BRL', () => {
    expect(formatCurrencyBRL(12000)).toBe('R$ 120,00')
  })

  it('retorna string vazia para valores nulos', () => {
    expect(formatCurrencyBRL(null)).toBe('')
    expect(formatCurrencyBRL(undefined)).toBe('')
  })
})

describe('formatDateBR', () => {
  it('converte YYYY-MM-DD para DD/MM/YYYY', () => {
    expect(formatDateBR('2026-09-10')).toBe('10/09/2026')
  })
})

describe('phone helpers', () => {
  it('normaliza dígitos removendo formatação', () => {
    expect(normalizePhoneDigits('(11) 98765-4321')).toBe('11987654321')
  })

  it('formata progressivamente enquanto o usuário digita', () => {
    expect(formatPhoneInput('11987654321')).toBe('(11) 98765-4321')
    expect(formatPhoneInput('119876')).toBe('(11) 9876')
    expect(formatPhoneInput('11')).toBe('11')
  })

  it('valida celular com DDD (10 ou 11 dígitos)', () => {
    expect(isValidBrPhone('(11) 98765-4321')).toBe(true)
    expect(isValidBrPhone('(11) 8765-4321')).toBe(true)
    expect(isValidBrPhone('12345')).toBe(false)
  })

  it('adiciona código do país 55 quando ausente', () => {
    expect(toApiPhone('(11) 98765-4321')).toBe('5511987654321')
    expect(toApiPhone('5511987654321')).toBe('5511987654321')
  })
})

describe('formatPhoneDisplay', () => {
  it('tira o DDI e formata o número salvo pela API', () => {
    expect(formatPhoneDisplay('5511999990000')).toBe('(11) 99999-0000')
  })

  it('funciona com número já sem DDI', () => {
    expect(formatPhoneDisplay('1133334444')).toBe('(11) 3333-4444')
  })
})

describe('hasPrice', () => {
  it('zero ou ausente não é preço para mostrar', () => {
    expect(hasPrice(0)).toBe(false)
    expect(hasPrice(null)).toBe(false)
    expect(hasPrice(undefined)).toBe(false)
    expect(hasPrice(1)).toBe(true)
  })
})
