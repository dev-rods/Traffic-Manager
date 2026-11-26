import { describe, expect, it } from 'vitest'
import { BRASIL, PAISES, ddiValido, formataNumero, montaTelefone, numeroValido, placeholderDoNumero } from './ddi'

describe('código do país (25/11/2026)', () => {
  it('Brasil é o primeiro da lista e segue a regra do celular brasileiro', () => {
    expect(PAISES[0].ddi).toBe(BRASIL)
    expect(numeroValido('55', '11999990000')).toBe(true)
    expect(numeroValido('55', '1133334444')).toBe(false)
    expect(montaTelefone('55', '11999990000')).toBe('5511999990000')
    expect(formataNumero('55', '11999990000')).toBe('(11) 99999-0000')
  })

  it('fora do Brasil aceita qualquer padrão numérico de 6 a 14 dígitos e manda com o +', () => {
    expect(numeroValido('1', '8184722644')).toBe(true)
    expect(montaTelefone('1', '(818) 472-2644')).toBe('+18184722644')
    expect(formataNumero('1', '818 472 2644')).toBe('8184722644')
    expect(numeroValido('351', '912345678')).toBe(true)
    expect(numeroValido('1', '12345')).toBe(false)
    expect(numeroValido('1', '123456789012345')).toBe(false)
  })

  it('código digitado à mão em "Outro" precisa de 1 a 3 dígitos', () => {
    expect(ddiValido('')).toBe(false)
    expect(ddiValido('1234')).toBe(false)
    expect(ddiValido('351')).toBe(true)
    expect(numeroValido('', '8184722644')).toBe(false)
    expect(montaTelefone('+45', '12345678')).toBe('+4512345678')
  })

  it('placeholder muda com o país', () => {
    expect(placeholderDoNumero('55')).toBe('(00) 00000-0000')
    expect(placeholderDoNumero('1')).toMatch(/Só os números/)
  })
})
