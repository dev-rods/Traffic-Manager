import { describe, it, expect } from 'vitest'
import {
  avisosDaAlteracao,
  linhasDaAlteracao,
  temEfeitoForaDaTela,
  textoDoDesconto,
  type AlteracaoPretendida,
} from './alteracaoDeAgendamento'
import type { Appointment } from '@/types'

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'ap1',
    clinic_id: 'c1',
    appointment_date: '2026-11-12',
    start_time: '09:00:00',
    confirmado_em: null,
    confirmado_por: null,
    payment_status: null,
    ...over,
  } as Appointment
}

describe('linhasDaAlteracao', () => {
  it('sem mudança, sem linha', () => {
    expect(linhasDaAlteracao({})).toEqual([])
    expect(temEfeitoForaDaTela({})).toBe(false)
  })

  it('mostra de -> para de cada campo com efeito fora da tela', () => {
    const a: AlteracaoPretendida = {
      data: { de: '2026-11-12', para: '2026-11-14' },
      horario: { de: '09:00', para: '15:00' },
    }
    expect(linhasDaAlteracao(a)).toEqual([
      { rotulo: 'Data', de: '2026-11-12', para: '2026-11-14' },
      { rotulo: 'Horário', de: '09:00', para: '15:00' },
    ])
    expect(temEfeitoForaDaTela(a)).toBe(true)
  })

  it('a ordem é a da tela, não a de inserção', () => {
    const a: AlteracaoPretendida = {
      desconto: { de: 'sem desconto', para: '20%' },
      data: { de: '2026-11-12', para: '2026-11-14' },
    }
    expect(linhasDaAlteracao(a).map((l) => l.rotulo)).toEqual(['Data', 'Desconto'])
  })

  it('cobre serviço, áreas, duração e desconto', () => {
    const a: AlteracaoPretendida = {
      servico: { de: 'Laser', para: 'Limpeza' },
      areas: { de: 'Axila', para: 'Axila, Virilha' },
      duracao: { de: 'calculada', para: '50 min' },
      desconto: { de: 'sem desconto', para: 'parceria (100%)' },
    }
    expect(linhasDaAlteracao(a).map((l) => l.rotulo)).toEqual([
      'Serviço',
      'Áreas',
      'Duração',
      'Desconto',
    ])
  })
})

describe('avisosDaAlteracao', () => {
  it('mudar horário avisa do slot liberado e de que a paciente não é avisada', () => {
    const avisos = avisosDaAlteracao(agendamento(), {
      horario: { de: '09:00', para: '15:00' },
    })
    expect(avisos).toHaveLength(2)
    expect(avisos[0]).toMatch(/horário anterior fica livre/i)
    expect(avisos[1]).toMatch(/não será avisada/i)
  })

  it('presença confirmada entra como terceiro aviso', () => {
    const avisos = avisosDaAlteracao(
      agendamento({ confirmado_em: '2026-11-10T10:00:00Z', confirmado_por: 'PACIENTE' }),
      { data: { de: '2026-11-12', para: '2026-11-14' } },
    )
    expect(avisos.some((t) => /voltará a Pendente/i.test(t))).toBe(true)
  })

  it('sem mudar horário, a presença confirmada não é mencionada', () => {
    const avisos = avisosDaAlteracao(
      agendamento({ confirmado_em: '2026-11-10T10:00:00Z' }),
      { desconto: { de: 'sem desconto', para: '20%' } },
    )
    expect(avisos.some((t) => /Pendente/i.test(t))).toBe(false)
  })

  it('desconto em agendamento pago avisa que o cobrado não muda', () => {
    const avisos = avisosDaAlteracao(agendamento({ payment_status: 'PAID' }), {
      desconto: { de: 'sem desconto', para: '20%' },
    })
    expect(avisos.some((t) => /já foi pago/i.test(t))).toBe(true)
  })

  it('desconto em agendamento NÃO pago não fala de dinheiro cobrado', () => {
    for (const status of ['PENDING', 'CANCELLED', null] as const) {
      const avisos = avisosDaAlteracao(agendamento({ payment_status: status }), {
        desconto: { de: 'sem desconto', para: '20%' },
      })
      expect(avisos).toEqual([])
    }
  })

  it('nada mudou, nada a avisar', () => {
    expect(avisosDaAlteracao(agendamento(), {})).toEqual([])
  })
})

describe('textoDoDesconto', () => {
  it.each([
    ['none', '', 'sem desconto'],
    ['partnership', '', 'parceria (100%)'],
    ['custom', '20', '20%'],
    ['custom', '', 'sem desconto'],
    ['custom', '0', 'sem desconto'],
  ] as const)('%s / %s -> %s', (modo, pct, esperado) => {
    expect(textoDoDesconto(modo, pct)).toBe(esperado)
  })
})
