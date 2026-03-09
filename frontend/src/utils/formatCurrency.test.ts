import { describe, it, expect } from 'vitest'
import { formatCurrency, discountAmount, applyDiscount } from './formatCurrency'

describe('formatCurrency', () => {
  it('formats cents to BRL', () => {
    expect(formatCurrency(18000)).toBe('R$\u00a0180,00')
  })

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('R$\u00a00,00')
  })

  it('formats values with cents', () => {
    expect(formatCurrency(18050)).toBe('R$\u00a0180,50')
  })

  it('formats large values', () => {
    expect(formatCurrency(100000)).toBe('R$\u00a01.000,00')
  })
})

describe('discountAmount', () => {
  it('calculates 20% discount', () => {
    expect(discountAmount(18000, 20)).toBe(3600)
  })

  it('calculates 10% discount', () => {
    expect(discountAmount(44000, 10)).toBe(4400)
  })

  it('returns 0 for no discount', () => {
    expect(discountAmount(18000, 0)).toBe(0)
  })
})

describe('applyDiscount', () => {
  it('applies 20% to 18000 → 14400', () => {
    expect(applyDiscount(18000, 20)).toBe(14400)
  })

  it('applies 10% to 44000 → 39600', () => {
    expect(applyDiscount(44000, 10)).toBe(39600)
  })

  it('returns original when no discount', () => {
    expect(applyDiscount(18000, 0)).toBe(18000)
  })
})
