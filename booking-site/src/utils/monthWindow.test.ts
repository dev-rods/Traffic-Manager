import { describe, expect, it } from 'vitest'
import { monthWindow } from './monthWindow'

describe('monthWindow', () => {
  it('vai de hoje até o último dia do mês', () => {
    const dates = monthWindow(new Date(2026, 9, 28, 15, 30))
    expect(dates).toEqual(['2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31'])
  })

  it('no último dia do mês é só hoje', () => {
    expect(monthWindow(new Date(2026, 9, 31))).toEqual(['2026-10-31'])
  })

  it('respeita fevereiro bissexto', () => {
    expect(monthWindow(new Date(2028, 1, 27))).toEqual(['2028-02-27', '2028-02-28', '2028-02-29'])
  })

  it('nunca passa de 31 datas (limite da API)', () => {
    expect(monthWindow(new Date(2026, 0, 1))).toHaveLength(31)
  })
})
