import { describe, expect, it } from 'vitest'
import {
  formatCpf,
  formatDateLong,
  formatPhone,
  isToday,
  isValidCpf,
  isValidMobile,
} from './format'

describe('format', () => {
  it('telefone', () => {
    expect(formatPhone('11999990000')).toBe('(11) 99999-0000')
    expect(isValidMobile('11999990000')).toBe(true)
    expect(isValidMobile('1133334444')).toBe(false)
  })

  it('CPF', () => {
    expect(formatCpf('52998224725')).toBe('529.982.247-25')
    expect(isValidCpf('52998224725')).toBe(true)
    expect(isValidCpf('52998224724')).toBe(false)
    expect(isValidCpf('11111111111')).toBe(false)
  })

  it('data', () => {
    expect(formatDateLong('2026-10-20')).toBe('terça, 20 de outubro')
    expect(isToday('2026-10-20', new Date(2026, 9, 20, 15))).toBe(true)
    expect(isToday('2026-10-21', new Date(2026, 9, 20, 15))).toBe(false)
  })
})
