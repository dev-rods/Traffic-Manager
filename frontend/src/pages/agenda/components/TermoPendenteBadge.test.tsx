import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TermoPendenteBadge } from './TermoPendenteBadge'
import type { Appointment } from '@/types'

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    status: 'CONFIRMED',
    consent_enabled: true,
    consent_status: null,
    consent_waived_at: null,
    consent_waived_reason: null,
    consent_waived_by: null,
    ...over,
  } as Appointment
}

describe('TermoPendenteBadge', () => {
  it('pendente confirmado mostra DOCS', () => {
    render(<TermoPendenteBadge appointment={agendamento()} />)
    expect(screen.getByText('DOCS')).toHaveAttribute('title', 'Termo e anamnese pendentes')
  })

  it('abriu o link e parou na assinatura: DOCS diz o que falta (PRD 065)', () => {
    render(<TermoPendenteBadge appointment={agendamento({ consent_status: 'SIGNING' })} />)
    expect(screen.getByText('DOCS')).toHaveAttribute('title', 'Falta assinar (abriu o link)')
  })

  it('parou na ficha: DOCS diz que falta a ficha', () => {
    render(<TermoPendenteBadge appointment={agendamento({ consent_status: 'FILLING' })} />)
    expect(screen.getByText('DOCS')).toHaveAttribute('title', 'Falta a ficha (abriu o link)')
  })

  it.each([
    ['assinado', { consent_status: 'SIGNED' as const }],
    ['em papel', { consent_status: 'PAPER' as const }],
    ['dispensado', { consent_waived_at: '2026-11-04T12:00:00Z' }],
    ['cancelado', { status: 'CANCELLED' as const }],
    ['sem versão configurada', { consent_enabled: false }],
  ])('%s: nada', (_, over) => {
    const { container } = render(<TermoPendenteBadge appointment={agendamento(over)} />)
    expect(container).toBeEmptyDOMElement()
  })
})
