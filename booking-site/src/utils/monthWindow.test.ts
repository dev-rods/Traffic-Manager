import { describe, expect, it } from 'vitest'
import { datesBetween, monthWindow } from './monthWindow'

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

describe('datesBetween', () => {
  it('vai de start até end, inclusive, virando o mês', () => {
    expect(datesBetween('2026-10-30', '2026-11-01')).toEqual([
      '2026-10-30',
      '2026-10-31',
      '2026-11-01',
    ])
  })

  it('end antes de start não dá nenhuma data', () => {
    expect(datesBetween('2026-11-01', '2026-10-31')).toEqual([])
  })

  it('nunca passa de 31 datas (limite da API)', () => {
    expect(datesBetween('2026-01-01', '2026-03-31')).toHaveLength(31)
  })
})
