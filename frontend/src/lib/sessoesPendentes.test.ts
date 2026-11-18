import { describe, it, expect } from 'vitest'
import type { SessaoSemRegistro } from '@/types'
import { ordenaPendentes, rotuloDaSessao, sessaoPreSelecionada } from './sessoesPendentes'

function s(id: string, appointment_date: string, start_time = '09:00:00'): SessaoSemRegistro {
  return { id, appointment_date, start_time, areas: '' }
}

describe('ordenaPendentes', () => {
  it('ordena da data mais recente para a mais antiga, futuras incluídas', () => {
    const r = ordenaPendentes([s('a', '2026-10-01'), s('b', '2026-11-08'), s('f', '2026-11-19')])
    expect(r.map((x) => x.id)).toEqual(['f', 'b', 'a'])
  })

  it('no mesmo dia, o horário mais tarde vem primeiro', () => {
    const r = ordenaPendentes([
      s('manha', '2026-11-10', '09:00:00'),
      s('tarde', '2026-11-10', '15:00:00'),
    ])
    expect(r.map((x) => x.id)).toEqual(['tarde', 'manha'])
  })

  it('não altera a lista recebida', () => {
    const entrada = [s('a', '2026-10-01'), s('b', '2026-11-08')]
    ordenaPendentes(entrada)
    expect(entrada.map((x) => x.id)).toEqual(['a', 'b'])
  })
})

describe('sessaoPreSelecionada', () => {
  it('pula as futuras e pega a mais recente até hoje', () => {
    const r = ordenaPendentes([s('f', '2026-11-19'), s('b', '2026-11-08'), s('a', '2026-10-01')])
    expect(sessaoPreSelecionada(r, '2026-11-10')?.id).toBe('b')
  })

  it('hoje conta (dia inteiro), mesmo com horário depois de agora', () => {
    const r = ordenaPendentes([s('hoje', '2026-11-10', '18:00:00'), s('b', '2026-11-08')])
    expect(sessaoPreSelecionada(r, '2026-11-10')?.id).toBe('hoje')
  })

  it('só futuras: nenhuma pré-selecionada', () => {
    const r = ordenaPendentes([s('f', '2026-11-19')])
    expect(sessaoPreSelecionada(r, '2026-11-17')).toBeUndefined()
  })
})

describe('rotuloDaSessao', () => {
  it('data brasileira e hora sem segundos', () => {
    expect(rotuloDaSessao(s('a', '2026-11-08', '09:30:00'))).toBe('08/11/2026 · 09:30')
  })
})
