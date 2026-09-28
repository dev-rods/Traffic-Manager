/**
 * Os vãos livres de um dia de agenda.
 *
 * A lista do celular mostrava só o que está marcado. Descobrir que das 10h às
 * 14h não há nada exigia subtrair horários de cabeça, linha a linha - e é
 * justamente o que se quer saber ao olhar a agenda no balcão.
 */
import { describe, expect, it } from 'vitest'
import { comoHora, duracaoPorExtenso, vaosLivres, type Vao } from './expediente'
import type { Appointment } from '@/types'

const DIA = { inicio: 7 * 60, fim: 22 * 60 }

let seq = 0
function atendimento(start: string, end: string, status = 'CONFIRMED'): Appointment {
  seq += 1
  return {
    id: `a-${seq}`,
    start_time: `${start}:00`,
    end_time: `${end}:00`,
    status,
  } as Appointment
}

/** "09:00-10:30", para as asserções lerem como a tela. */
function legivel(vaos: Vao[]): string[] {
  return vaos.map((v) => `${comoHora(v.inicio)}-${comoHora(v.fim)}`)
}

describe('vaosLivres', () => {
  it('acha o buraco entre dois atendimentos', () => {
    const vaos = vaosLivres(
      [atendimento('09:00', '10:00'), atendimento('14:00', '15:00')],
      DIA,
    )

    expect(legivel(vaos)).toEqual(['07:00-09:00', '10:00-14:00', '15:00-22:00'])
  })

  it('não inventa vão onde os atendimentos se encostam', () => {
    const vaos = vaosLivres(
      [atendimento('09:00', '10:00'), atendimento('10:00', '11:00')],
      DIA,
    )

    expect(legivel(vaos)).toEqual(['07:00-09:00', '11:00-22:00'])
  })

  it('ignora vão menor que o mínimo', () => {
    // 10 minutos entre as sessões: não cabe nada, e listar polui a tela
    const vaos = vaosLivres(
      [atendimento('09:00', '10:00'), atendimento('10:10', '11:00')],
      DIA,
    )

    expect(legivel(vaos)).toEqual(['07:00-09:00', '11:00-22:00'])
  })

  it('aceita vão exatamente do tamanho mínimo', () => {
    const vaos = vaosLivres(
      [atendimento('09:00', '10:00'), atendimento('10:15', '11:00')],
      DIA,
    )

    expect(legivel(vaos)).toContain('10:00-10:15')
  })

  it('não abre vão fantasma com atendimento dentro de outro', () => {
    // A grade do desktop distribui simultâneos em colunas; aqui o risco é o
    // cursor seguir o ÚLTIMO da lista e abrir 14:45-15:00 como livre.
    const vaos = vaosLivres(
      [atendimento('14:00', '15:00'), atendimento('14:30', '14:45')],
      DIA,
    )

    expect(legivel(vaos)).toEqual(['07:00-14:00', '15:00-22:00'])
  })

  it('lida com atendimentos que se sobrepõem parcialmente', () => {
    const vaos = vaosLivres(
      [atendimento('09:00', '10:30'), atendimento('10:00', '11:00')],
      DIA,
    )

    expect(legivel(vaos)).toEqual(['07:00-09:00', '11:00-22:00'])
  })

  it('cancelado não ocupa horário', () => {
    const vaos = vaosLivres(
      [atendimento('09:00', '10:00', 'CANCELLED'), atendimento('14:00', '15:00')],
      DIA,
    )

    expect(legivel(vaos)).toEqual(['07:00-14:00', '15:00-22:00'])
  })

  it('atendimento antes da janela empurra o cursor', () => {
    // Começou 06:30 e vai até 08:00: as 7h não estão livres, ainda que a
    // sessão comece fora do que a tela desenha.
    const vaos = vaosLivres([atendimento('06:30', '08:00')], DIA)

    expect(legivel(vaos)).toEqual(['08:00-22:00'])
  })

  it('atendimento que passa do fim da janela não gera vão negativo', () => {
    const vaos = vaosLivres([atendimento('21:00', '23:30')], DIA)

    expect(legivel(vaos)).toEqual(['07:00-21:00'])
  })

  it('dia inteiro livre é um vão só', () => {
    expect(legivel(vaosLivres([], DIA))).toEqual(['07:00-22:00'])
  })

  it('dia inteiro ocupado não tem vão', () => {
    expect(vaosLivres([atendimento('07:00', '22:00')], DIA)).toEqual([])
  })

  it('não depende da ordem de entrada', () => {
    const fora = vaosLivres(
      [atendimento('14:00', '15:00'), atendimento('09:00', '10:00')],
      DIA,
    )

    expect(legivel(fora)).toEqual(['07:00-09:00', '10:00-14:00', '15:00-22:00'])
  })
})

describe('comoHora', () => {
  it.each([
    [7 * 60, '07:00'],
    [9 * 60 + 5, '09:05'],
    [22 * 60, '22:00'],
    [0, '00:00'],
  ])('%i vira %s', (minutos, esperado) => {
    expect(comoHora(minutos)).toBe(esperado)
  })
})

describe('duracaoPorExtenso', () => {
  it.each([
    [45, '45 min'],
    [60, '1h'],
    [90, '1h30'],
    [65, '1h05'],
    [240, '4h'],
  ])('%i min vira %s', (minutos, esperado) => {
    expect(duracaoPorExtenso(minutos)).toBe(esperado)
  })
})
