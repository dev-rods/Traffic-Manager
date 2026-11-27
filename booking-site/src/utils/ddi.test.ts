import { describe, expect, it } from 'vitest'
import { BRASIL, OUTRO, PAISES, numeroValido, paisDoNumero, valorDoSite } from './ddi'
import { isValidPhone, toApiPhone } from './format'

// Mesmos vetores em checkin e frontend (PRD 067).
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
    expect(numeroValido('1234', '2025550147')).toBe(false)
  })

  it('a string do site segue o contrato de sempre com a API', () => {
    expect(valorDoSite('55', '11987654321')).toBe('(11) 98765-4321')
    expect(valorDoSite('1', '2025550147')).toBe('+12025550147')
    expect(valorDoSite('1', '202')).toBe('')
    expect(toApiPhone(valorDoSite('55', '11987654321'))).toBe('5511987654321')
    expect(toApiPhone(valorDoSite('1', '2025550147'))).toBe('+12025550147')
    expect(isValidPhone(valorDoSite('1', '202555'))).toBe(true)
    expect(isValidPhone(valorDoSite('1', '202'))).toBe(false)
  })
})

describe('país de um número gravado (PRD 067)', () => {
  it('brasileiro com e sem o 55, inclusive formatado', () => {
    expect(paisDoNumero('5511999990000')).toEqual({ pais: BRASIL, ddiLivre: '', digits: '11999990000' })
    expect(paisDoNumero('(11) 98765-4321')).toEqual({ pais: BRASIL, ddiLivre: '', digits: '11987654321' })
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
