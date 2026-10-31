import { describe, expect, it } from 'vitest'
import {
  brDateToIso,
  formatCpf,
  formatDateInput,
  isValidBirthDate,
  isValidCpf,
  isValidEmail,
  listaDeCampos,
} from './cadastro'

describe('CPF', () => {
  it.each([
    ['529.982.247-25', true],
    ['52998224725', true],
    ['11111111111', false],
    ['12345678900', false],
    ['123', false],
  ])('%s -> %s', (cpf, esperado) => {
    expect(isValidCpf(cpf)).toBe(esperado)
  })

  it('formata enquanto digita', () => {
    expect(formatCpf('529')).toBe('529')
    expect(formatCpf('5299822')).toBe('529.982.2')
    expect(formatCpf('52998224725999')).toBe('529.982.247-25')
  })
})

describe('data de nascimento', () => {
  it('formata enquanto digita', () => {
    expect(formatDateInput('3')).toBe('3')
    expect(formatDateInput('3110')).toBe('31/10')
    expect(formatDateInput('31101990')).toBe('31/10/1990')
  })

  it.each([
    ['31/10/1990', '1990-10-31'],
    ['29/02/2024', '2024-02-29'],
    ['31/02/2024', null],
    ['1990-10-31', null],
    ['', null],
  ])('%s -> %s', (br, iso) => {
    expect(brDateToIso(br)).toBe(iso)
  })

  it('aceita passado e recusa futuro ou antes de 1900', () => {
    expect(isValidBirthDate('31/10/1990')).toBe(true)
    expect(isValidBirthDate('01/01/2099')).toBe(false)
    expect(isValidBirthDate('01/01/1850')).toBe(false)
    expect(isValidBirthDate('31/02/2024')).toBe(false)
  })
})

describe('e-mail', () => {
  it.each([
    ['maria@x.com', true],
    [' Maria@X.com ', true],
    ['maria', false],
    ['maria@', false],
    ['ma ria@x.com', false],
  ])('%s -> %s', (email, esperado) => {
    expect(isValidEmail(email)).toBe(esperado)
  })
})

describe('listaDeCampos', () => {
  it('junta em português', () => {
    expect(listaDeCampos(['cpf'])).toBe('CPF')
    expect(listaDeCampos(['cpf', 'email'])).toBe('CPF e e-mail')
    expect(listaDeCampos(['birth_date', 'cpf', 'email'])).toBe('data de nascimento, CPF e e-mail')
  })
})
