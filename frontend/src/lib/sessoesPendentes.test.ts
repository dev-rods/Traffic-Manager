import { describe, it, expect } from 'vitest'
import type { SessaoSemRegistro } from '@/types'
import { rotuloDaSessao, sessoesPendentesAteHoje } from './sessoesPendentes'

function s(id: string, appointment_date: string, start_time = '09:00:00'): SessaoSemRegistro {
  return { id, appointment_date, start_time, areas: '' }
}

describe('sessoesPendentesAteHoje', () => {
  it('ordena da mais próxima de hoje para a mais antiga', () => {
    const r = sessoesPendentesAteHoje(
      [s('a', '2026-10-01'), s('b', '2026-11-08'), s('c', '2026-10-20')],
      '2026-11-10',
    )
    expect(r.map((x) => x.id)).toEqual(['b', 'c', 'a'])
  })

  it('inclui hoje (dia inteiro) e exclui o futuro', () => {
    const r = sessoesPendentesAteHoje(
      [s('hoje', '2026-11-10', '18:00:00'), s('amanha', '2026-11-11')],
      '2026-11-10',
    )
    expect(r.map((x) => x.id)).toEqual(['hoje'])
  })

  it('no mesmo dia, o horário mais tarde vem primeiro', () => {
    const r = sessoesPendentesAteHoje(
      [s('manha', '2026-11-10', '09:00:00'), s('tarde', '2026-11-10', '15:00:00')],
      '2026-11-10',
    )
    expect(r.map((x) => x.id)).toEqual(['tarde', 'manha'])
  })
})

describe('rotuloDaSessao', () => {
  it('data brasileira e hora sem segundos', () => {
    expect(rotuloDaSessao(s('a', '2026-11-08', '09:30:00'))).toBe('08/11/2026 · 09:30')
  })
})
