import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgendaDoDia } from './AgendaDoDia'
import type { Appointment } from '@/types'

/**
 * A lista que substitui a grade em celular.
 *
 * O que ela precisa entregar, e a grade não entregava em 375px: ordem
 * cronológica óbvia, áreas e duração visíveis sem um toque a mais, e linhas
 * grandes o suficiente para o dedo.
 */
function agendamento(over: Partial<Appointment>): Appointment {
  return {
    id: Math.random().toString(),
    appointment_date: '2026-09-23',
    start_time: '09:00:00',
    end_time: '09:15:00',
    status: 'CONFIRMED',
    patient_name: 'Ana Clara',
    areas: 'Axilas',
    duration_minutes: 15,
    is_first_visit: false,
    ...over,
  } as Appointment
}

const clique = vi.fn()

describe('AgendaDoDia', () => {
  it('ordena por horário, e não pela ordem que veio da API', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ start_time: '15:00:00', patient_name: 'Tarde' }),
          agendamento({ start_time: '09:00:00', patient_name: 'Manha' }),
          agendamento({ start_time: '11:30:00', patient_name: 'Meio' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    const nomes = screen.getAllByRole('button').map((b) => b.textContent)
    expect(nomes[0]).toContain('Manha')
    expect(nomes[1]).toContain('Meio')
    expect(nomes[2]).toContain('Tarde')
  })

  it('mostra áreas e duração sem exigir um toque', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ areas: 'Virilha Completa + ânus', duration_minutes: 25 })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText('Virilha Completa + ânus')).toBeInTheDocument()
    expect(screen.getByText(/25 min/)).toBeInTheDocument()
  })

  it('marca a duração ajustada à mão', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ duration_minutes: 10, manual_duration_minutes: 10 })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText(/ajustada/)).toBeInTheDocument()
  })

  it('só mostra o dia pedido', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[
          agendamento({ patient_name: 'Do dia' }),
          agendamento({ appointment_date: '2026-09-24', patient_name: 'De outro dia' }),
        ]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.getByText('Do dia')).toBeInTheDocument()
    expect(screen.queryByText('De outro dia')).not.toBeInTheDocument()
  })

  it('cancelado não aparece, como na grade', () => {
    render(
      <AgendaDoDia
        dia="2026-09-23"
        appointments={[agendamento({ status: 'CANCELLED', patient_name: 'Cancelada' })]}
        onAppointmentClick={clique}
      />,
    )

    expect(screen.queryByText('Cancelada')).not.toBeInTheDocument()
    expect(screen.getByText(/Nenhum atendimento/)).toBeInTheDocument()
  })

  it('dia vazio explica, em vez de mostrar uma caixa em branco', () => {
    render(<AgendaDoDia dia="2026-09-23" appointments={[]} onAppointmentClick={clique} />)

    expect(screen.getByText(/Nenhum atendimento neste dia/)).toBeInTheDocument()
  })

  it('tocar na linha devolve o agendamento', async () => {
    const onClick = vi.fn()
    const alvo = agendamento({ patient_name: 'Larissa' })
    render(
      <AgendaDoDia dia="2026-09-23" appointments={[alvo]} onAppointmentClick={onClick} />,
    )

    await userEvent.click(screen.getByRole('button'))

    expect(onClick.mock.calls[0][0]).toBe(alvo)
  })
})
