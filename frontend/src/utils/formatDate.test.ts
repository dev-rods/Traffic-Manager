import { describe, it, expect } from 'vitest'
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
