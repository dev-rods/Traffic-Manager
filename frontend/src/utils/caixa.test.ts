import { describe, it, expect } from 'vitest'
import { intervaloDa } from './caixa'

describe('intervaloDa', () => {
  const hoje = new Date(2026, 9, 19, 15)

  it('hoje, ontem, 7 dias e mês, no calendário local', () => {
    expect(intervaloDa('hoje', hoje)).toEqual(['2026-10-19', '2026-10-19'])
    expect(intervaloDa('ontem', hoje)).toEqual(['2026-10-18', '2026-10-18'])
    expect(intervaloDa('7dias', hoje)).toEqual(['2026-10-13', '2026-10-19'])
    expect(intervaloDa('mes', hoje)).toEqual(['2026-10-01', '2026-10-19'])
  })

  it('ontem no dia 1º volta para o mês anterior', () => {
    expect(intervaloDa('ontem', new Date(2026, 10, 1))).toEqual(['2026-10-31', '2026-10-31'])
  })
})
