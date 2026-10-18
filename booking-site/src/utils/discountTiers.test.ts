import { describe, expect, it } from 'vitest'
import { nextTierHint, tiersSummary } from './discountTiers'
import type { DiscountTier } from '@/types'

const TIERS: DiscountTier[] = [
  { minAreas: 2, maxAreas: 3, pct: 10 },
  { minAreas: 4, maxAreas: null, pct: 20 },
]

describe('tiersSummary', () => {
  it('lista as faixas', () => {
    expect(tiersSummary(TIERS)).toBe('2 a 3 áreas: 10% off · 4 ou mais áreas: 20% off')
  })

  it('faixa de um número só', () => {
    expect(tiersSummary([{ minAreas: 2, maxAreas: 2, pct: 10 }])).toBe('2 áreas: 10% off')
  })

  it('sem faixas não anuncia nada', () => {
    expect(tiersSummary([])).toBeNull()
  })
})

describe('nextTierHint', () => {
  it('antes da primeira área, nada', () => {
    expect(nextTierHint(TIERS, 0)).toBeNull()
  })

  it('falta uma área para a primeira faixa', () => {
    expect(nextTierHint(TIERS, 1)).toBe('Falta 1 área para 10% de desconto')
  })

  it('dentro da primeira faixa aponta a próxima', () => {
    expect(nextTierHint(TIERS, 2)).toBe('Faltam 2 áreas para 20% de desconto')
    expect(nextTierHint(TIERS, 3)).toBe('Falta 1 área para 20% de desconto')
  })

  it('na última faixa, nada', () => {
    expect(nextTierHint(TIERS, 4)).toBeNull()
    expect(nextTierHint(TIERS, 9)).toBeNull()
  })

  it('sem faixas, nada', () => {
    expect(nextTierHint([], 1)).toBeNull()
  })
})
