import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AppointmentPopover } from './AppointmentPopover'
import type { Appointment } from '@/types'

vi.mock('@/hooks/useCaixa', () => ({
  useReceberDinheiro: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false, data: undefined }),
  useEnviarLink: () => ({ mutate: vi.fn(), isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

/**
 * Reagendado não é cancelado (PRD 035). O registro antigo fica CANCELLED, mas
 * com `rescheduled_to_id`: a pessoa continua marcada, noutro dia. O popover
 * diz isso em cor neutra e leva ao dia novo.
 */
function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    appointment_date: '2026-10-21',
    start_time: '09:00:00',
    end_time: '09:15:00',
    status: 'CANCELLED',
    patient_name: 'Ana Clara',
    areas: 'Axilas',
    duration_minutes: 15,
    is_first_visit: false,
    rescheduled_to_id: null,
    rescheduled_to_date: null,
    ...over,
  } as Appointment
}

function monta(over: Partial<Appointment> = {}) {
  const props = {
    onClose: vi.fn(),
    onEdit: vi.fn(),
    onCancel: vi.fn(),
    onMarcarFalta: vi.fn(),
    onDesmarcarFalta: vi.fn(),
    onNavigateToDate: vi.fn(),
  }
  render(
    <AppointmentPopover
      appointment={agendamento(over)}
      anchorRect={{ top: 0, right: 0 } as DOMRect}
      {...props}
    />,
  )
  return props
}

describe('agendamento remarcado no popover', () => {
  it('diz para quando foi remarcado, em vez de "Cancelado"', () => {
    monta({ rescheduled_to_id: 'a2', rescheduled_to_date: '2026-10-22' })

    expect(screen.getByText('Remarcado para 22/10')).toBeInTheDocument()
    expect(screen.queryByText('Cancelado')).not.toBeInTheDocument()
  })

  it('"Ver novo" leva a agenda ao dia novo e fecha', async () => {
    const props = monta({ rescheduled_to_id: 'a2', rescheduled_to_date: '2026-10-22' })

    await userEvent.click(screen.getByText('Ver novo'))

    expect(props.onNavigateToDate).toHaveBeenCalledWith('2026-10-22')
    expect(props.onClose).toHaveBeenCalled()
  })

  it('cancelado de verdade segue "Cancelado", sem "Ver novo"', () => {
    monta()

    expect(screen.getByText('Cancelado')).toBeInTheDocument()
    expect(screen.queryByText('Ver novo')).not.toBeInTheDocument()
  })
})
