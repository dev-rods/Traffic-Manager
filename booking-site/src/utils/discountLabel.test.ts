import { describe, expect, it } from 'vitest'
import { discountLabel } from './discountLabel'

describe('discountLabel', () => {
  it('traduz cada motivo', () => {
    expect(discountLabel('first_session', 1)).toBe('Primeira sessão')
    expect(discountLabel('tier_2', 3)).toBe('3 áreas')
    expect(discountLabel('tier_3', 5)).toBe('5 áreas')
    expect(discountLabel('personalizado', 1)).toBe('Desconto especial')
  })

  it('sem motivo não tem rótulo', () => {
    expect(discountLabel(null, 2)).toBeNull()
  })
})
