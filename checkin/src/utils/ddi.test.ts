import { describe, expect, it } from 'vitest'
import { BRASIL, OUTRO, PAISES, ddiValido, formataNumero, montaTelefone, numeroValido, paisDoNumero, placeholderDoNumero } from './ddi'

describe('código do país (25/11/2026)', () => {
  it('Brasil é o primeiro da lista e segue a regra do celular brasileiro', () => {
    expect(PAISES[0].ddi).toBe(BRASIL)
    expect(numeroValido('55', '11999990000')).toBe(true)
    expect(numeroValido('55', '1133334444')).toBe(false)
    expect(montaTelefone('55', '11999990000')).toBe('5511999990000')
    expect(formataNumero('55', '11999990000')).toBe('(11) 99999-0000')
  })

  it('fora do Brasil aceita qualquer padrão numérico de 6 a 14 dígitos e manda com o +', () => {
    expect(numeroValido('1', '2025550147')).toBe(true)
    expect(montaTelefone('1', '(202) 555-0147')).toBe('+12025550147')
    expect(formataNumero('1', '202 555 0147')).toBe('2025550147')
    expect(numeroValido('351', '912345678')).toBe(true)
    expect(numeroValido('1', '12345')).toBe(false)
    expect(numeroValido('1', '123456789012345')).toBe(false)
  })

  it('código digitado à mão em "Outro" precisa de 1 a 3 dígitos', () => {
    expect(ddiValido('')).toBe(false)
    expect(ddiValido('1234')).toBe(false)
    expect(ddiValido('351')).toBe(true)
    expect(numeroValido('', '2025550147')).toBe(false)
    expect(montaTelefone('+45', '12345678')).toBe('+4512345678')
  })

  it('placeholder muda com o país', () => {
    expect(placeholderDoNumero('55')).toBe('(00) 00000-0000')
    expect(placeholderDoNumero('1')).toMatch(/Só os números/)
  })
})

// Mesmos vetores em booking-site e frontend (PRD 067).
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
