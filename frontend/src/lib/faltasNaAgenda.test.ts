import { describe, it, expect } from 'vitest'
import { semFaltas, contaFaltas } from './faltasNaAgenda'
import type { Appointment } from '@/types'

function a(status: Appointment['status'], id = Math.random().toString()): Appointment {
  return { id, status, appointment_date: '2026-10-01' } as Appointment
}

describe('semFaltas', () => {
  it('tira as faltas e preserva o resto', () => {
    const lista = [a('CONFIRMED', '1'), a('NO_SHOW', '2'), a('CONFIRMED', '3')]

    expect(semFaltas(lista).map((x) => x.id)).toEqual(['1', '3'])
  })

  it('não mexe no cancelado', () => {
    // Quem filtra cancelado são os componentes da agenda, e continua sendo
    // deles. Duplicar aqui criaria dois lugares decidindo o mesmo.
    const lista = [a('CANCELLED', '1'), a('NO_SHOW', '2')]

    expect(semFaltas(lista).map((x) => x.id)).toEqual(['1'])
  })

  it('devolve lista vazia sem reclamar', () => {
    expect(semFaltas([])).toEqual([])
  })

  it('não muta a lista recebida', () => {
    // A lista vem do cache do TanStack Query: mutar aqui corromperia o que
    // outras telas leem do mesmo cache.
    const lista = [a('NO_SHOW', '1'), a('CONFIRMED', '2')]

    semFaltas(lista)

    expect(lista).toHaveLength(2)
  })
})

describe('contaFaltas', () => {
  it('conta só as faltas', () => {
    expect(contaFaltas([a('NO_SHOW'), a('NO_SHOW'), a('CONFIRMED'), a('CANCELLED')])).toBe(2)
  })

  it('zero quando não há nenhuma', () => {
    // É o caso que faz a linha "N faltas ocultas" não aparecer.
    expect(contaFaltas([a('CONFIRMED'), a('CANCELLED')])).toBe(0)
  })

  it('zero em lista vazia', () => {
    expect(contaFaltas([])).toBe(0)
  })
})
