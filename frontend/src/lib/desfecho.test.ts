import { describe, expect, it } from 'vitest'
import { aberturaDoDia, desfechoAutomatico, desfechoDe, explicaDesfecho, nomeDoDesfecho } from './desfecho'
import type { AvailabilityRule } from '@/types'

function regra(over: Partial<AvailabilityRule>): AvailabilityRule {
  return {
    id: 'r', clinic_id: 'c', day_of_week: null, rule_date: null,
    start_time: '09:00:00', end_time: '18:00:00', professional_id: null, active: true,
    ...over,
  }
}

// 2026-11-25 é quarta-feira (getDay() = 3).
const QUARTA = '2026-11-25'

describe('aberturaDoDia', () => {
  it('a regra mais cedo do dia da semana', () => {
    const regras = [regra({ day_of_week: 3, start_time: '13:00:00' }), regra({ day_of_week: 3, start_time: '09:00:00' })]
    expect(aberturaDoDia(regras, QUARTA, '15:00:00')).toBe('09:00')
  })

  it('data fixa vence a recorrente; regra inativa não conta', () => {
    const regras = [
      regra({ day_of_week: 3, start_time: '09:00:00' }),
      regra({ rule_date: QUARTA, start_time: '11:00:00' }),
      regra({ rule_date: QUARTA, start_time: '08:00:00', active: false }),
    ]
    expect(aberturaDoDia(regras, QUARTA, '15:00:00')).toBe('11:00')
  })

  it('sem regra para o dia, vale a hora da sessão', () => {
    expect(aberturaDoDia([regra({ day_of_week: 1 })], QUARTA, '15:00:00')).toBe('15:00')
    expect(aberturaDoDia(undefined, QUARTA, '15:00:00')).toBe('15:00')
  })
})

describe('desfechoAutomatico', () => {
  it('24 h antes da abertura ainda é cancelamento; um minuto depois é falta', () => {
    expect(desfechoAutomatico(new Date('2026-11-24T09:00:00'), QUARTA, '09:00')).toBe('CANCELLED')
    expect(desfechoAutomatico(new Date('2026-11-24T08:59:00'), QUARTA, '09:00')).toBe('CANCELLED')
    expect(desfechoAutomatico(new Date('2026-11-24T09:01:00'), QUARTA, '09:00')).toBe('NO_SHOW')
  })

  it('a referência é a abertura da agenda, não a hora da sessão', () => {
    // Sessão às 15h, agenda abre às 9h: às 10h do dia anterior já é falta.
    const regras = [regra({ day_of_week: 3, start_time: '09:00:00' })]
    const a = { appointment_date: QUARTA, start_time: '15:00:00' }
    expect(desfechoDe(regras, a, new Date('2026-11-24T10:00:00'))).toBe('NO_SHOW')
    expect(desfechoDe(regras, a, new Date('2026-11-24T08:30:00'))).toBe('CANCELLED')
    // Sem regra, a hora da sessão manda.
    expect(desfechoDe([], a, new Date('2026-11-24T10:00:00'))).toBe('CANCELLED')
  })

  it('sessão passada é falta', () => {
    expect(desfechoAutomatico(new Date('2026-11-26T10:00:00'), QUARTA, '09:00')).toBe('NO_SHOW')
  })
})

describe('textos', () => {
  it('nome e explicação', () => {
    expect(nomeDoDesfecho('NO_SHOW')).toBe('falta')
    expect(nomeDoDesfecho('CANCELLED')).toBe('cancelamento')
    expect(explicaDesfecho('NO_SHOW')).toMatch(/Vai contar como falta/)
    expect(explicaDesfecho('CANCELLED')).toMatch(/Vai contar como cancelamento/)
  })
})
