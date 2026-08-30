/**
 * Rótulo das datas no seletor de agendamento.
 *
 * O input de data livre deixava marcar sessão em dia sem atendimento. A lista
 * passa a ter só as datas cadastradas em Horários, e o rótulo precisa dizer o
 * dia da semana: quem agenda pensa em "terça", não em "23/09".
 */
import { describe, it, expect } from 'vitest'
import { formatDateOption } from './formatDateOption'

describe('formatDateOption', () => {
  it('escreve o dia da semana e a data por extenso', () => {
    expect(formatDateOption('2026-09-23')).toBe('Quarta, 23 de setembro')
  })

  it('não usa fuso do navegador: 23/09 não pode virar 22/09', () => {
    // Data ISO pura é interpretada como UTC pelo Date; em fuso negativo isso
    // recua um dia e a clínica veria a data errada na lista.
    expect(formatDateOption('2026-01-01')).toBe('Quinta, 1 de janeiro')
  })

  it('inclui o ano quando a data cai em outro ano', () => {
    expect(formatDateOption('2027-03-08', '2026-08-30')).toBe('Segunda, 8 de março de 2027')
  })

  it('omite o ano no ano corrente', () => {
    expect(formatDateOption('2026-03-08', '2026-08-30')).toBe('Domingo, 8 de março')
  })
})
