import { describe, it, expect } from 'vitest'
import { formatDateBR, formatDayMonth, formatShortDateBR } from './formatDate'
import { agoraEmSaoPaulo, todayStr } from './dateHelpers'
import { dataDe, horaDe } from './pagamento'

describe('datas no fuso de São Paulo', () => {
  // 02:00 UTC de 18/11 ainda é 23:00 de 17/11 em São Paulo: foi assim que a
  // assinatura do E2E de 17/11/2026 apareceu como 18/11.
  const iso = '2026-11-18T02:00:17Z'
  it('timestamp vira o dia de São Paulo, não o de UTC', () => {
    expect(formatDateBR(iso)).toBe('17/11/2026')
    expect(formatDayMonth(iso)).toBe('17/11')
    expect(formatShortDateBR(iso)).toBe('17/11/26')
    expect(dataDe(iso)).toBe('17/11')
    expect(horaDe(iso)).toBe('23:00')
  })
  it('hoje é o dia de São Paulo', () => {
    const esperado = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/Sao_Paulo',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date())
    expect(todayStr()).toBe(esperado)
    expect(agoraEmSaoPaulo().getDate()).toBe(Number(esperado.slice(8, 10)))
  })
})
import { formatDate, formatDateOnly, formatTime, formatShortDate } from './formatDate'

// Fixed ISO string: 2026-03-08 12:00 UTC = 09:00 BRT
const ISO = '2026-03-08T12:00:00.000Z'

describe('formatDate', () => {
  it('formats to Brazilian date', () => {
    const result = formatDate(ISO)
    expect(result).toMatch(/8/)
    expect(result).toMatch(/2026/)
    expect(result.toLowerCase()).toMatch(/mar/)
  })
})

describe('formatTime', () => {
  it('formats to HH:MM in BRT', () => {
    const result = formatTime(ISO)
    expect(result).toBe('09:00')
  })
})

describe('formatShortDate', () => {
  it('includes weekday and date', () => {
    const result = formatShortDate(ISO)
    // 2026-03-08 is a Sunday (dom)
    expect(result.toLowerCase()).toMatch(/dom/)
    expect(result).toMatch(/8/)
  })
})

describe('formatDateOnly', () => {
  it('keeps the calendar day of a plain date', () => {
    expect(formatDateOnly('2026-11-20')).toBe('20 de nov de 2026')
  })

  it('does not shift to the previous day at month and year boundaries', () => {
    expect(formatDateOnly('2026-12-01')).toBe('1 de dez de 2026')
    expect(formatDateOnly('2027-01-01')).toBe('1 de jan de 2027')
  })
})
