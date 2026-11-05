import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfirmacaoBadge } from './ConfirmacaoBadge'
import type { Appointment } from '@/types'

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    status: 'CONFIRMED',
    lembrete_enviado_em: null,
    confirmado_em: null,
    confirmado_por: null,
    ...over,
  } as Appointment
}

describe('ConfirmacaoBadge', () => {
  it('sem lembrete e sem confirmação: nada (não houve pergunta)', () => {
    const { container } = render(<ConfirmacaoBadge appointment={agendamento()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lembrete enviado sem resposta: PENDENTE', () => {
    render(
      <ConfirmacaoBadge
        appointment={agendamento({ lembrete_enviado_em: '2026-11-05T10:00:00Z' })}
      />
    )
    expect(screen.getByText('PENDENTE')).toHaveAttribute('title', 'Lembrete enviado, sem resposta')
  })

  it('confirmada pela equipe ANTES do lembrete: CONFIRMADO mesmo assim', () => {
    render(
      <ConfirmacaoBadge
        appointment={agendamento({
          confirmado_em: '2026-11-05T10:00:00Z',
          confirmado_por: 'EQUIPE',
        })}
      />
    )
    expect(screen.getByText('CONFIRMADO')).toHaveAttribute(
      'title',
      'Presença confirmada pela equipe'
    )
  })

  it('confirmada pela paciente depois do lembrete: CONFIRMADO', () => {
    render(
      <ConfirmacaoBadge
        appointment={agendamento({
          lembrete_enviado_em: '2026-11-05T10:00:00Z',
          confirmado_em: '2026-11-05T11:00:00Z',
          confirmado_por: 'PACIENTE',
        })}
      />
    )
    expect(screen.getByText('CONFIRMADO')).toHaveAttribute(
      'title',
      'Presença confirmada pela paciente'
    )
  })

  it('cancelado ou falta: nada', () => {
    const { container } = render(
      <ConfirmacaoBadge
        appointment={agendamento({ status: 'NO_SHOW', confirmado_em: '2026-11-05T10:00:00Z' })}
      />
    )
    expect(container).toBeEmptyDOMElement()
  })
})
