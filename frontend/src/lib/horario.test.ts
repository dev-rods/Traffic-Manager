import { describe, it, expect } from 'vitest'
import { ehHorarioValido } from './horario'

describe('ehHorarioValido', () => {
  it('aceita horário do dia', () => {
    for (const h of ['00:00', '07:45', '12:30', '23:59']) {
      expect(ehHorarioValido(h)).toBe(true)
    }
  })

  it('recusa hora que não existe', () => {
    for (const h of ['24:00', '25:30', '99:99']) {
      expect(ehHorarioValido(h)).toBe(false)
    }
  })

  it('recusa minuto que não existe', () => {
    expect(ehHorarioValido('10:60')).toBe(false)
    expect(ehHorarioValido('10:99')).toBe(false)
  })

  // O campo é digitável agora: o que chega colado não passa pelo teclado do
  // `<input type="time">`, e uma hora malformada só apareceria como erro do
  // backend, longe de quem digitou.
  it('recusa formato solto', () => {
    for (const h of ['7:45', '0745', '07h45', '07:45:00', '7:5']) {
      expect(ehHorarioValido(h)).toBe(false)
    }
  })

  it('recusa vazio e ausente', () => {
    expect(ehHorarioValido('')).toBe(false)
    expect(ehHorarioValido(null)).toBe(false)
    expect(ehHorarioValido(undefined)).toBe(false)
  })
})
