import { describe, expect, it } from 'vitest'
import { BRASIL, OUTRO, PAISES, numeroValido, paisDoNumero, telefoneDaApi } from './ddi'
import { normalizePhone } from './normalizePhone'

// Mesmos vetores em checkin e booking-site (PRD 067).
describe('código do país (PRD 067)', () => {
  it('Brasil é o primeiro da lista; DDD + número com 10 ou 11 dígitos', () => {
    expect(PAISES[0].ddi).toBe(BRASIL)
    expect(numeroValido('55', '11999990000')).toBe(true)
    expect(numeroValido('55', '1133334444')).toBe(true)
    expect(numeroValido('55', '119999')).toBe(false)
  })

  it('fora do Brasil: 6 a 14 dígitos e código de 1 a 3', () => {
    expect(numeroValido('1', '2025550147')).toBe(true)
    expect(numeroValido('351', '912345678')).toBe(true)
    expect(numeroValido('1', '12345')).toBe(false)
    expect(numeroValido('1', '123456789012345')).toBe(false)
    expect(numeroValido('', '2025550147')).toBe(false)
  })

  it('o que vai para a API: 55 no Brasil, + fora, vazio se incompleto', () => {
    expect(telefoneDaApi('55', '11999990000')).toBe('5511999990000')
    expect(telefoneDaApi('1', '2025550147')).toBe('+12025550147')
    expect(telefoneDaApi('1', '202')).toBe('')
  })
})

describe('país de um número gravado (PRD 067)', () => {
  it('brasileiro com e sem o 55', () => {
    expect(paisDoNumero('5511999990000')).toEqual({ pais: BRASIL, ddiLivre: '', digits: '11999990000' })
    expect(paisDoNumero('11999990000')).toEqual({ pais: BRASIL, ddiLivre: '', digits: '11999990000' })
    expect(paisDoNumero('551133334444')).toEqual({ pais: BRASIL, ddiLivre: '', digits: '1133334444' })
  })

  it('estrangeiro pelo prefixo mais longo da lista, com ou sem +', () => {
    expect(paisDoNumero('12025550147')).toEqual({ pais: '1', ddiLivre: '', digits: '2025550147' })
    expect(paisDoNumero('+351912345678')).toEqual({ pais: '351', ddiLivre: '', digits: '912345678' })
    expect(paisDoNumero('+5491123456789')).toEqual({ pais: '54', ddiLivre: '', digits: '91123456789' })
  })

  it('fora da lista vira Outro com o número inteiro; vazio é Brasil', () => {
    expect(paisDoNumero('4512345678')).toEqual({ pais: BRASIL, ddiLivre: '', digits: '4512345678' })
    expect(paisDoNumero('+4512345678')).toEqual({ pais: OUTRO, ddiLivre: '', digits: '4512345678' })
    expect(paisDoNumero(null)).toEqual({ pais: BRASIL, ddiLivre: '', digits: '' })
  })
})

describe('normalizePhone com número de fora (PRD 067)', () => {
  it('com + não acrescenta 55', () => {
    expect(normalizePhone('+12025550147')).toBe('12025550147')
    expect(normalizePhone('+1 (202) 555-0147')).toBe('12025550147')
  })

  it('brasileiro continua igual', () => {
    expect(normalizePhone('11999990000')).toBe('5511999990000')
    expect(normalizePhone('5511999990000')).toBe('5511999990000')
    expect(normalizePhone('+5511999990000')).toBe('5511999990000')
    expect(normalizePhone('011999990000')).toBe('5511999990000')
  })
})
